# Quickstart: Medications CRUD

To start developing this feature:

1. Bring up the development stack:
   ```bash
   just dev
   ```

2. Run backend tests to verify existing state:
   ```bash
   just test
   ```

3. Ensure frontend dependencies are up-to-date (if modified):
   ```bash
   cd frontend && pnpm install
   ```

4. After adding/modifying the backend API, regenerate the OpenAPI client:
   ```bash
   just generate-client
   ```

5. When DB models are added, generate the Alembic migration:
   ```bash
   just migrate-rev "Add medications and schedules"
   just migrate
   ```
