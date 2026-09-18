using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.Json;
using QuantConnect.Data;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;

namespace QuantConnect.Algorithm.CSharp
{
    // Research-only deterministic fixture for cross-engine validation.
    public class FrozenPathResearchAlgorithm : QCAlgorithm
    {
        private Symbol _spy;
        private int _barIndex;
        private readonly List<FillRecord> _fills = new();

        private sealed class FillRecord
        {
            public long TsNs { get; set; }
            public decimal Price { get; set; }
            public decimal Quantity { get; set; }
            public decimal Fee { get; set; }
        }

        public override void Initialize()
        {
            SetStartDate(2013, 10, 7);
            SetEndDate(2013, 10, 7);
            SetCash(ParseDecimalEnv("LEAN_VALIDATION_INITIAL_CAPITAL", 100000m));

            SetSecurityInitializer(security =>
            {
                security.SetDataNormalizationMode(DataNormalizationMode.Raw);
                security.SetFeeModel(new ConstantFeeModel(0));
            });

            _spy = AddEquity("SPY", Resolution.Hour).Symbol;
        }

        public override void OnData(Slice slice)
        {
            if (!slice.Bars.ContainsKey(_spy))
            {
                return;
            }

            // These are execution-bar indices after the frozen one-bar lag.
            if (_barIndex == 1)
            {
                MarketOrder(_spy, ParseDecimalEnv("LEAN_VALIDATION_QUANTITY", 1m));
            }
            else if (_barIndex == 3)
            {
                MarketOrder(_spy, -ParseDecimalEnv("LEAN_VALIDATION_QUANTITY", 1m));
            }

            _barIndex++;
        }

        public override void OnOrderEvent(OrderEvent orderEvent)
        {
            if (orderEvent.Status != OrderStatus.Filled)
            {
                return;
            }

            var utc = DateTime.SpecifyKind(orderEvent.UtcTime, DateTimeKind.Utc);
            var unixNs = new DateTimeOffset(utc).ToUnixTimeMilliseconds() * 1_000_000L;
            _fills.Add(new FillRecord
            {
                TsNs = unixNs,
                Price = orderEvent.FillPrice,
                Quantity = orderEvent.FillQuantity,
                Fee = Math.Abs(orderEvent.OrderFee.Value.Amount)
            });
        }

        public override void OnEndOfAlgorithm()
        {
            if (_fills.Count != 2)
            {
                throw new InvalidOperationException(
                    $"Frozen LEAN fixture expected exactly 2 fills, got {_fills.Count}"
                );
            }
            if (Portfolio.Invested)
            {
                throw new InvalidOperationException("Frozen LEAN fixture ended invested");
            }

            var entry = _fills[0];
            var exit = _fills[1];
            if (entry.Quantity <= 0 || exit.Quantity >= 0)
            {
                throw new InvalidOperationException("Frozen LEAN fixture direction mismatch");
            }

            var size = Math.Abs(entry.Quantity);
            var fees = entry.Fee + exit.Fee;
            var pnl = (exit.Price - entry.Price) * size - fees;
            var fingerprint = Environment.GetEnvironmentVariable("LEAN_CONTRACT_FINGERPRINT");
            var output = Environment.GetEnvironmentVariable("LEAN_EVIDENCE_PATH");
            var runId = Environment.GetEnvironmentVariable("LEAN_RUN_ID");

            if (string.IsNullOrWhiteSpace(fingerprint) || string.IsNullOrWhiteSpace(output)
                || string.IsNullOrWhiteSpace(runId))
            {
                throw new InvalidOperationException("LEAN evidence environment is incomplete");
            }

            var payload = new
            {
                executed = true,
                run_id = runId,
                contract_fingerprint = fingerprint,
                execution_mode = "lean_source_launcher",
                research_only = true,
                trade_authority = false,
                promotion_authority = false,
                bars_processed = _barIndex,
                trades = new[]
                {
                    new
                    {
                        direction = "long",
                        entry_ts = entry.TsNs,
                        exit_ts = exit.TsNs,
                        entry_price = (double)entry.Price,
                        exit_price = (double)exit.Price,
                        size = (double)size,
                        fees = (double)fees,
                        pnl = (double)pnl
                    }
                }
            };

            var fullPath = Path.GetFullPath(output);
            Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
            File.WriteAllText(fullPath, JsonSerializer.Serialize(payload));
        }

        private static decimal ParseDecimalEnv(string name, decimal fallback)
        {
            var raw = Environment.GetEnvironmentVariable(name);
            return decimal.TryParse(
                raw,
                NumberStyles.Number,
                CultureInfo.InvariantCulture,
                out var value
            ) ? value : fallback;
        }
    }
}
