# Worker diagnostics privacy boundary

Failed worker subprocesses may emit stack traces containing request details. The runtime diagnostics path therefore follows these rules:

- capture stderr only into the job's temporary directory;
- read only a bounded tail after non-zero exit;
- redact common credential, bearer-token, API-key and JWT forms before storage or logging;
- keep the sanitized excerpt only in the private runtime incident ledger and private Render application logs;
- public worker/coordinator snapshots expose only error type, classification and deterministic diagnostic/incident fingerprints;
- diagnostics have no trade, signal, promotion, repository-write or deployment authority.
