<!--Based on Best README Template -->
<!--See: https://github.com/othneildrew/Best-README-Template/pull/73-->
<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]

<!-- Introduction -->
# CTI Data Processing (cti-sys)
Welcome to the repository! The goal of this project is to maintain an efficient and robust data sytem for managing CTI operations, ranging from student tracking, reporting, and ensuring consistency across our programs.

CTI stands for [Computing Talent Initiative][website-url]. A program spearheaded by [Prof. Sathya Narayanan][director-url], the goal is to provide pathways for students to successfully transition from higher education into a successful career in the industry. CTI uses a mix of online courses, workshops, and hands-on experiences to prepare students for real-world development.

This project is primarily being developed internally and for internal use. Many planning documents are internal as well, so if you're interested in contributing, please contact the repository owner, [Nicolas Guerrero][owner-email].

## Getting Started

### Build Instructions

#### Database Set-Up
You'll need both a PostgreSQL Database and a MongoDB Database. You'll also need admin permissions to set-up the tables/collections. Make sure you have the following connection strings set (either through a env file, Heroku's conifg vars, or an environment variable). Additionally, if you are building from scratch, make sure to install the requirements.txt, since you'll need SQLAlchemy and Pymongo to run the initialization scripts.

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
1. Create a virtual environment and install the requirements.txt
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
Please check our contributing guide. As mentioned in the introduction, the project's not looking for new members outside the organization due to the onboarding time, but you can contact us if you're really interested in this project.

## Roadmap
TODO

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->

<!-- Top Shield Links -->
[contributors-shield]: https://img.shields.io/github/contributors/github_username/repo_name.svg?style=for-the-badge
[contributors-url]: https://github.com/github_username/repo_name/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/github_username/repo_name.svg?style=for-the-badge
[forks-url]: https://github.com/github_username/repo_name/network/members
[stars-shield]: https://img.shields.io/github/stars/github_username/repo_name.svg?style=for-the-badge
[stars-url]: https://github.com/github_username/repo_name/stargazers
[issues-shield]: https://img.shields.io/github/issues/github_username/repo_name.svg?style=for-the-badge
[issues-url]: https://github.com/github_username/repo_name/issues
[license-shield]: https://img.shields.io/github/license/github_username/repo_name.svg?style=for-the-badge
[license-url]: https://github.com/github_username/repo_name/blob/master/LICENSE.txt

<!-- Logos & Site Links -->
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/

[Fast-API]: https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png
[Fast-API-url]: https://fastapi.tiangolo.com/

<!-- Contact URLs -->
[website-url]: https://computingtalentinitiative.org/accelerate/
[director-url]: https://www.linkedin.com/in/sathyanarayanan6/
[owner-email]: mailto:nicguerrero@csumb.edu