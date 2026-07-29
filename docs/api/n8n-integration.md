# n8n integration

Use n8n as an integration and scheduling layer.

Recommended flow:

```text
Schedule Trigger
  -> HTTP POST /api/v1/sync/jobs
  -> store job_id
  -> end execution
```

Do not keep an n8n execution open while tens of thousands of listings are processed. Do not write directly to `hqa_db`, `sync_db`, or `identity_db`.
