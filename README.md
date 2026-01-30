# AutoRia Used Cars Scraper

This project collects data about used cars from AutoRia and saves it into a PostgreSQL database. It also performs daily database dumps.

The scraper is fully **asynchronous** and uses **parallel workers** with `asyncio.gather()` and `Semaphore` for efficient concurrent processing.

---

## Quick Start

1. **Clone the repository**

   Use Git to clone the repository and enter the project folder.
```bash
 git clone https://github.com/SerhiiBasok/dataox-test-task
```


2. **Create a `.env` file**

   Copy the example `.env.sample` to `.env` and configure your settings:

   > Set `BASE_URL` to the AutoRia used cars start page, and configure other settings like database credentials, scraper schedule, and dump times.

3. **Start the project**

   Use Docker Compose to build and start all services, including the scraper, database, and dumper.
```bash
docker-compose up --build
```
---

## Check Parsed Data

To view the parsed cars data:

- Connect to the PostgreSQL database container.
- Run SQL queries on the `cars` table to inspect the data.

```bash
 docker exec -it dataox-test-task-postgres-1 psql -U admin -d cars_db -c "\x" -c "SELECT * FROM cars;"
```


---

## Manual Database Dump

To run a manual database dump:

- Execute the dumper service.
- The dump file will be saved in the `dumps/` folder at the project root.

```bash
docker compose run --rm dumper python -m app.dumper.run_dump_now
```


---

## Notes

* All settings are stored in the `.env` file.
* Duplicate entries are removed at the database level.
* Parser uses configurable number of workers (`WORKERS` env variable) for parallel processing.
* The project fully meets the requirements of the DataOx test task.
