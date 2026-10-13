# Deployment

## Local HTTP and HTTPS behind a proxy

Local development uses `SESSION_COOKIE_SECURE=false` and `PROXY_HOPS=0`, so you can sign in at `http://localhost:5000`.

For HTTPS behind **one trusted reverse proxy**, put the following in the server's private `.env`:

```dotenv
SESSION_COOKIE_SECURE=true
PROXY_HOPS=1
TRUSTED_HOSTS=panel.example.com
```

Replace the example hostname on the server. Do not publish your deployment address or real `.env`. Keep the original Host header. Have the proxy replace X-Forwarded-For and set X-Forwarded-Proto to the browser's original protocol. Restrict the backend port to the trusted proxy or your private network so direct clients cannot supply trusted forwarding headers.

PROXY_HOPS is the actual number of trusted proxies; leave it at zero for direct connections. Forwarded host, port and prefix headers are not trusted.

Cookies always use HttpOnly and SameSite=Lax. In HTTPS mode they also use Secure and will not be sent over plain HTTP. Redirect public HTTP to HTTPS. All forms require CSRF tokens; HTTPS form submissions also require a matching origin.

These settings do not change student codes, bot bindings or results. Replacing the Flask secret invalidates existing panel sessions. Recreate the panel after changing its environment:

```sh
docker compose up -d --build web_teacher_panel
```

The panel uses one Gunicorn worker. Authentication limits live in each process's memory and reset on restart. Use shared persistent limiting storage before deploying multiple workers or replicas.

## Database permissions

| Role | Permissions |
| --- | --- |
| admin | Database ownership and maintenance; never used by the apps. |
| english4u_web | Read teachers, students, units, words, results; insert teachers through the CLI; create/edit/delete students, units and words; use relevant ID sequences. |
| english4u_bot | Read students, units, words, results and results_view; update only students.telegram_user_id; insert results and update only request/answer counters; use the results ID sequence. |

Application roles have CONNECT and schema USAGE without superuser, schema/table creation, role administration or TRUNCATE. Signed-in teachers manage one shared workspace; separate classrooms are not implemented.

## Existing databases

Back up the database and private configuration first. New databases initialize roles automatically. Existing databases need grants applied using configured secrets:

```sh
docker compose exec -T postgres sh /scripts_sql/init_app_roles.sh
```

Changing POSTGRES_ADMIN_PASSWORD in Compose alone does not rotate an existing password. Run psql as admin inside the database container and set the role's password to the container's configured value:

```sql
\getenv new_password POSTGRES_PASSWORD
SELECT format('ALTER ROLE admin PASSWORD %L', :'new_password') \gexec
```

Do not run demonstration imports or clear_base.sql against data you want to keep. Database files, dumps, .env and backups stay outside Git and Docker build contexts.

## Recovery

Keep dumps and .env in a directory readable only by the administrator. Test restoring to a separate database. Stop the bot before a production restore to prevent writes during recovery.

Learning counters and Telegram bindings are saved in PostgreSQL. Current questions and authorization prompts live in memory; after a restart, students may need to select their unit again.

## Test on the current bot before pushing to GitHub

The local and server checkouts use the same GitHub repository as origin. The live server is also the place for the owner's manual acceptance check.

1. Edit locally, run the regression tests, review the diff and commit the candidate on main. A local commit does not publish it.
2. Optionally run the build and regression tests on the server first:

   ```sh
   python3 scripts/check_on_server.py --ssh-target YOUR_SSH_ALIAS
   ```

   This helper uses temporary images and containers without networking, with test-only credentials. It leaves the live app unchanged and cleans up its temporary files. Changes to schemas, grants or migrations need checks against a PostgreSQL copy as well.
3. Make sure the live checkout is clean and a current backup is available. Send the committed candidate directly over SSH, without pushing it to GitHub yet:

   ```sh
   git bundle create /tmp/english4u-release.bundle main
   scp /tmp/english4u-release.bundle YOUR_SSH_ALIAS:/tmp/english4u-release.bundle
   ```

4. On the server, in the application checkout:

   ```sh
   git status --short
   git fetch /tmp/english4u-release.bundle main
   git merge --ff-only FETCH_HEAD
   docker compose up -d --build web_teacher_panel telegram_bot
   ```

   Stop if there are unrelated working changes or the fast-forward fails. Do not reset over someone else's work.
5. Check HTTPS panel login and forms, a real bot game, /words and /stop, and container logs. If the candidate fails, return the code and images to the previous version; restore the database backup only when a data change requires it.
6. After the owner's server check succeeds, publish from the local checkout:

   ```sh
   git push origin main
   ```

   Then run `git fetch origin` on the server to update its tracking reference. All three copies now have the tested commit. GitHub Actions provides another check after publication.

For reviewed feature work, test the feature branch on the server before publishing its branch and opening a pull request. Merge only the tested revision and synchronize main afterwards. A push alone does not automatically deploy changes to production.
