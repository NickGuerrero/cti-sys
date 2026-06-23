<!--Based on Best README Template -->
<!--See: https://github.com/othneildrew/Best-README-Template/pull/73-->
<a id="readme-top"></a>

<!-- Introduction -->
# CTI Data Processing (cti-sys)
Welcome to the repository! The goal of this project is to maintain an efficient and robust data sytem for managing CTI operations, ranging from student tracking, reporting, and ensuring consistency across our programs.

CTI stands for [Computing Talent Initiative][website-url]. A program spearheaded by [Prof. Sathya Narayanan][director-url], the goal is to provide pathways for students to successfully transition from higher education into a successful career in the industry. CTI uses a mix of online courses, workshops, and hands-on experiences to prepare students for real-world development.

## Archival Update 06-23-2026
This project is no longer being supported. This project had been used throughout the 2025 - 2026 academic year for CTI's Accelerate program, handling record management for ~800 applications and ~400 active students. With Accelerate's retirement and CTI's de-emphasis on large headcounts, this system has no more planned releases for the foreseeable future. Thanks to the contributors that helped make this project possible.

You can fork or use this project as you see fit, according to the project's MIT license. Any further inquiries on the project may be sent to [Nicolas Guerrero][owner-email].

## Getting Started

### Build Instructions

#### Database Set-Up
You'll need both a PostgreSQL Database and a MongoDB Database. You'll also need admin permissions to set-up the tables/collections. Make sure you have the following connection strings set (either through a env file, Heroku's conifg vars, or an environment variable). Additionally, if you are building from scratch, make sure to install the uv dependencies, since you'll need SQLAlchemy and Pymongo to run the initialization scripts.

If you are part of the development team, you should have received a .env file with credentials for the development databases.
```
CTI_POSTGRES_URL="postgresql+psycopg://USER:PASS@HOST:PORT/DATABASE?sslmode=require"
CTI_MONGO_URL="mongodb+srv://USER:PASS@HOST/DATABASE?tls=true&retryWrites=true&w=majority&authSource=admin&replicaSet=REPLICASET&appName=APP"
```

#### Postgres Set-Up
1. Run the create_database.py script ```python -m src.db_scripts.create_database.py```
2. (Optional): Add test data (Will be prepared for the development team at a later time)

#### MongoDB Set-Up
Currently, the database is automatically created on deploy, along with collections. This database will persist, so as long as you have the correct admin permissions, there should not be any direct action needed at this time.

#### Heroku Deployment (Easy Method)
1. Create a new Heroku app (If you're part of the Heroku team, the app has already been created for you)
2. Go to Deploy. Connect your Heroku account with your GitHub account
3. Under Manual Deploy, you can select which branch you want to deploy
4. After Heroku finishes building the deployed changes, you will be provided the application URL
Everything should be handled by the Procfile, so look there if you need to modify runtime.

#### Local Deployment
1. Create a virtual environment and install the uv.lock dependencies
2. Make sure the environment variables are set
3. You can run the application either through FastAPI directly, or with Gunicorn (Not Windows)
```
// Running FastAPI directly
fastapi dev ./path/to/main.py

// Running Gunicorn (default)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app
```
4. Your application should be hosted through localhost, your shell should return a URL

## Contributing
Please check our contributing guide. We're currently not accepting contributions, if you're interested in continuing this project, considering forking.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->

<!-- Logos & Site Links -->
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/

[Fast-API]: https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png
[Fast-API-url]: https://fastapi.tiangolo.com/

<!-- Contact URLs -->
[website-url]: https://computingtalentinitiative.org/accelerate/
[director-url]: https://www.linkedin.com/in/sathyanarayanan6/
[owner-email]: mailto:nicguerrero@csumb.edu