# Building Automation System
In this repository, a building automation system is implemented three times in three different architectural styles.

Each module is a small, working system that we extend with new features while respecting the constraints of the style.

This was a course project for **DIT349 Fundamentals of Software Architecture course (University of Gothenburg)**, done in a group of 3.

| Module | Architecture style | What it does | Team member responsible |
| --- | ---- | ---- | ---- |
| Module 1 | Pipe-and-Filter | Cleans raw sensor readings and raises alarms through a chain of independent filters | [Aynan Tazrian](https://github.com/taazriiann) |
| Module 2 | Microservices | Device, reading, alert, authentication, auditing services behind an API gateway. One database per service | Shrinidhi Ganapathi |
| Module 3 | Publish-subscribe | Event bus with a broker, sensor publishers, dashboard, alarm monitor, and energy logger | [Josefina Faundez Reyes](https://github.com/jojosefin) |

<br>

> [!NOTE]
> Each module has its own README with how to run it, architecture, design decisions, and [diagrams](https://github.com/Shrinidhi253/ArchitectureStyles/tree/main/diagrams).

## Why this project is interesting:

The project has the same domain across the 3 modules, but they have very different structures. The project does not focus on the individual features, rather on the tradeoffs with each architecture style.

- **Pipe-and-Filter:** makes adding a processing step cheap, because filters only know their input and output pipes. But the style gets uncomfortable with stateful filters.

- **Microservices:** keep data ownership clear (one database per service). Cross-cutting concerns such as authentication and audit logging can be attached in one place, the gateway. Changes to data that are related to other services are the expensive ones.

- **Publish-Subscribe:** decouples components completely, because nobody knows who else is connected.

## Repository layout
```
diagram/                #diagrams for each module design
module1-pipeline/
module2-microservices/
module3-pubsub/
screencast-recordings/  #explanation and demo video for each module
```

Each module is **self-contained** and has its own tests. (`python -m pytest -q`).

The code was continuously integrated through gitlab CI pipeline.

## Requirements:
- [Python 3.10+](https://www.python.org/downloads/)
- Module 2 additionally needs Flask: `pip install -r requirements.txt` inside the module

## Usage of AI:
- AI assistants were used for code explanation, syntax-understanding, debugging, and drafting documentation.
- However, the diagrams and discussions are our own work. The team has also demonstrated understanding of the design decisions and code in the [`screencast-recordings`](https://github.com/Shrinidhi253/ArchitectureStyles/tree/main/screencast-recordings) and group interview session.