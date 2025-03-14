<a id="contributing-top"></a>

# Introduction

Thanks for your interest in our project. Contribution is generally done by our internal development team. As an open source project, you're allowed to download and use the project as you wish, but you can contact the repository owner in you're interested in contributing.

## Code Style
These rules are not all-encompassing, new rules may be created as more code is reviewed. However, here's a general set of coding styling and practices that are recommended when writing code for this project. I've based it off the PEP 8 styling guide, which has more in-depth recommendations (https://peps.python.org/pep-0008/).

### Naming Conventions
* Class names should be PascalCase (Student, SessionFactory, etc.)
* Function and variables names should be snake_case (active_user, update_time_commitment)
* Endpoint names should kebab-case and lowercase (/api/test-connection, /api/accelerate/process-attendance)
* Endpoint names and functions names should match (/api/applications/export-canvas-csv -> applications.export_canvas_csv())
* **IMPORTANT**: Avoid using the same name multiple times in the same file if they refer to 2 different things. It makes it much harder to read at a glance.
```
# Don't do this
some_var = 0
def my_func(some_var):
    return some_var + 1

```

### Importing
* For importing files in the project
    * Be explicit about what you import, absolute import preferred. Do not use wildcard imports.
    * Wildcard imports are only permitted in situations where everything needs to be accessed (e.g. database creation)
    ```
    from src.app.models.postgres.models import Student, Accelerate
    user = Student(...)
    ```
* For importing external libraries
    * Import rules are relaxed, absolute is still preferred
    ```
    import datetime
    today = datetime.datetime(...)
    ```


### Additional Styling Notes
* 4-spaces over tabs. You can set up your editor to automatically turn tabs into 4-spaces
* Lines should be under 100 characters.
* Variable and function definitions should be relatively close to where they're used. If a variable is used across the whole file (similar to how an import functon gets called at the top), you may keep towards the top of its scope.
* Don't call anything out of scope. If you need something outside a function, declare it as a parameter. If you need something outside the file, declare it in imports.
```
# Don't do this
some_var = 0
def my_func():
    return some_var
```

## Project Structure

### Endpoint & Domain-driven Organization

Folder structure is driven by the aggregate model(s) for each domain as well as the API endpoint paths. A shortened representation of the structure:
| **Path**                     |
|------------------------------|
| `src/`                        |
| ├── `applications/`           |
| ├── `students/`               |
| │   ├── `alternate_emails/`   |
| │   ├── `accelerate/`         |
| │   │   ├── `assign_sa_all/`  |

Endpoint paths used to define structure an domains:
| Path                                | HTTP Method |
|-------------------------------------|--------------|
| **applications/**                   | POST       |
| └── canvas-export                   | GET         |
| **students/**                       |             |
| ├── process-commitment              | POST        |
| ├── process-attendance-log          | POST        |
| ├── process-withdrawal              | POST        |
| ├── alternate-emails                | POST        |
| ├── check-activity                  | POST        |
| ├── **{id}/**                       |             |
| │   ├── recover-attendance          | POST        |
| │   └── mark-inactive/key={pass}    | POST        |
| └── **accelerate/**                 |             |
|     ├── assign-sa                   | PUT         |
|     ├── process-attendance          | POST        |
|     ├── process-canvas              | POST        |
|     ├── update-time-commitment      | PUT         |
|     └── assign-sa-all               | PUT         |
| **system/**                         |             |
| └── clean-inactive-requests         | POST        |

### Domain Content

Not every domain will require each of the following files. Define these as they are needed.

| **Path**             | **Description**                                           |
|----------------------|-----------------------------------------------------------|
| `applications/`       | **Domain**                                                |
| ├── `canvas_export/`  | Sub-domain `"canvas-export"`                              |
| ├── `config.py`       | Configuration file for the `applications` domain          |
| ├── `flows.py`        | Workflow functions that require multiple services and/or functions (more dependencies) |
| ├── `models.py`       | Pydantic classes for MongoDB documents or *Postgres DTOs   |
| ├── `router.py`       | Endpoint definitions under `"{url}/api/applications"`     |
| ├── `schemas.py`      | Pydantic classes for request and response data validation       |
| ├── `service.py`      | Business logic, CRUD operations (fewer dependencies)        |
| └── `util.py`         | Utility functions used solely within the `applications` domain |

*PostgreSQL tables as defined through SQLAlchemy classes are **only** located at `src/database/postgres/models.py` and additional SQLAlchemy entities should **not** be defined within specific domain `models.py` files.

### Large Services

Not all domains can be defined from the endpoint paths. A large, internally defined service, such as an emailing service, would be defined within its own domain (ex: `src/email`). All models and schemas, routers, service functions, configuration, and other functionality specific to this aggregate should be located in this service's domain.

### Testing

* Testing file structure should closely mirror that of the `src` directory
* Integration tests should be marked with `@pytest.mark.integration` and not be run within GitHub Actions
* Fixtures used for dependencies should be added to `conftest.py` and will not need to be manually imported to pytest files

## Repository Management

### Creating Issues
* Several Issue templates are provided for labeling work that needs to be done in the project
* Task: Direct assignments from the design doc and are generally created by the repository manager
* Bug Report: If there are bugs that pop up unexpectedly. You can report bugs even if you don't intend to address them.
* Feature Request: If you want add something, report it under issues first

As a rule of thumb, if the issue isn't assigned, you're free to work on it. Everyone on the development team should have at least 1 assigned issue at a time, so everyone knows what to work on.

### Branch Names
Branch names should follow this format: ```GitHubUsername/your-change```
* Start each branch name with your GitHub username to make it easy to identify branch owners
* The branch name should be related to its assigned issue or descriptive of its purpose
* Use hyphens (-) for spaces (kebab-case). In general, names should be around 2 - 4 words long. Keep words all in lowercase unless you're referring to a Proper Noun.

### Pull Request Review
Here's what the pull request process looks like:
1. The file changes are manually checked. Changes should be clear and easy to read through, and the pull request should provide context and an explanation to those changes.
2. Tests are then verified. Pull requests are automatically tested, but here the individual tests are looked through. Coverage should include at least 2 successful tests & 1 failure tests, but more may be needed. If the automated unit tests are not able to cover the pull request, it should be specified.
3. The branch is tested on a Heroku deployment, similar to the production environment. Please make sure your branch is updated with main to avoid any potential issues.
4. The deployment is tested on common endpoints. Full system tests would be run here. In pre-release development, just make sure that the application builds properly.
5. The review is written up, comments added, and the pull request is squashed onto the main branch. Branches are deleted after successful pull requests, so be aware of that in case you wanted to keep the branch.

Additional Notes
* We're not focusing on individual commits. Commits should provide context on why changes were made, but when they're ultimately squashed, commits not dierctly related or insignificant to the change are removed. This means 2 things - make as many commits as you want, and try to keep your commit headers descriptive.
* On the other hand, keep the number of actual changes relatively contained. Each change has to be reviewed, and version history is at its best when it's incremental. Each pull request should only focus on the proposed change. Any attempts to sneak in refactors, surprise tests, or exposed credentials will be rejected.


<p align="right">(<a href="#contributing-top">back to top</a>)</p>