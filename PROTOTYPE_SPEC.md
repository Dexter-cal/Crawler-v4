# Prototype Specification: Crawler Phase 1

## 1. Introduction

This document outlines the technical specification for **Phase 1** of the **Crawler** platform, as defined in the `ROADMAP.md`. The purpose of this phase is to build and validate the foundational components of the system, including a modular implant, a command and control (C2) server, and the core ethical governance frameworks (EOCF and ROE).

## 2. Core Architecture

The Phase 1 system consists of two primary components: the Command & Control (C2) server and the Implant.

### 2.1. Command & Control (C2) Server

*   **Functionality**: A lightweight web server that listens for connections from implants.
*   **API**: Exposes a RESTful API for implant registration, tasking, and data exfiltration.
*   **Implant Management**: Maintains a list of active implants and their assigned **ROE Tier** in memory.
*   **Operator Interface**: A command-line interface (CLI) to issue commands, respecting the ROE policies.

### 2.2. Implant

*   **Functionality**: A standalone Python script that runs on the target Linux machine.
*   **Plugin-Based**: The implant itself is a core agent that loads and manages various data collection modules (plugins).
*   **Beaconing**: Periodically sends a "heartbeat" request to the C2 server for new tasks.
*   **Task Execution**: Executes tasks by invoking methods on its loaded plugins.

## 3. Plugin Architecture

To ensure modularity and extensibility, all surveillance capabilities in the implant are implemented as plugins.

### 3.1. Plugin API Schema

Plugins must be Python classes that inherit from a common `BasePlugin` and implement the following interface:

```python
class BasePlugin:
    def get_name(self) -> str:
        # Return the unique name of the plugin (e.g., "keylogger")
        pass

    def start(self):
        # Start the data collection process (e.g., in a background thread)
        pass

    def stop(self):
        # Stop the data collection process
        pass

    def get_data(self) -> list:
        # Collect and return any captured data, then clear the internal buffer
        pass
```

### 3.2. Initial Plugin

*   **`keylogger.py`**: The first plugin, which will capture keystrokes using the `pynput` library.

## 4. Technology Stack

*   **Programming Language**: **Python 3.9+**
*   **C2 Server Framework**: **FastAPI**
*   **Implant Libraries**: `requests`, `pynput`
*   **Authorization**: `PyJWT` for issuing and validating EOCF tokens.
*   **Dependencies**: Managed via `requirements.txt`.

## 5. Project File Structure

```
crawler/
├── c2/
│   ├── __init__.py
│   ├── main.py
│   ├── api.py
│   ├── models.py
│   ├── cli.py
│   └── security.py      # EOCF token generation/validation
├── implant/
│   ├── __init__.py
│   ├── agent.py
│   ├── plugins/         # Renamed from 'modules'
│   │   ├── __init__.py
│   │   ├── base_plugin.py # Defines the BasePlugin class
│   │   └── keylogger.py
│   └── utils.py
├── requirements.txt
└── README.md
```

## 6. Communication Protocol (API)

### 6.1. Cryptographic Future-Proofing

Phase 1 will use standard HTTPS (TLS) for secure communication. However, the communication handlers will be designed to allow for the replacement of the transport layer with a **Quantum-Resistant Cryptographic** suite in a future phase.

### 6.2. `POST /api/register`

*   **Purpose**: To register a new implant and receive an authorization token.
*   **Request Body**: `{ "hostname": "...", "os": "...", "pid": ... }`
*   **Response Body**: Returns the implant's assigned ID and a JWT for authentication.
    ```json
    {
      "implant_id": "...",
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

### 6.3. `GET /api/tasks/{implant_id}`

*   **Purpose**: To fetch new commands. The implant must include its JWT in the `Authorization: Bearer <token>` header.
*   **Response Body**: A list of tasks.
    ```json
    { "tasks": [{ "task_id": "...", "command": "start_plugin", "args": {"plugin_name": "keylogger"} }] }
    ```

### 6.4. `POST /api/data/{implant_id}`

*   **Purpose**: To exfiltrate data. Requires JWT authorization.
*   **Request Body**: `{ "plugin": "keylogger", "data": "..." }`
*   **Response Body**: `{ "status": "received" }`

## 7. Governance Frameworks

### 7.1. Embedded Oversight Compliance Framework (EOCF) v1

*   **Authorization**: All API endpoints (except `/register`) are protected. Implants must authenticate using a short-lived JWT issued by the C2. The C2 will validate the token's signature and expiration on every request.
*   **Immutable Logging**: The C2 server must be configurable to stream structured audit logs (commands issued, data received, operator actions) to an external, append-only logging endpoint (e.g., a remote Syslog server or a dedicated log service). This decouples logging from the C2's local storage.

### 7.2. Rules of Engagement (ROE) v1

*   **Target Tiering**: The C2 will maintain an in-memory mapping of `implant_id` to an **ROE Tier** (1, 2, or 3). This tier is assigned by the operator via the CLI.
*   **Command Gating**: The C2's CLI will enforce rules based on the target's tier before sending a task to the implant. For example:
    *   **Tier 1 (Hostile Foreign Adversary)**: All plugins and commands are permitted.
    *   **Tier 2 (Suspected Operative)**: Destructive or manipulative plugins are forbidden.
    *   **Tier 3 (Domestic/Protected)**: Only passive, pre-approved data collection is allowed. The `keylogger` may be restricted.

## 8. Testing Notes

During integration testing in the development environment, the `keylogger` plugin was temporarily substituted with a `dummy_plugin`. This was necessary because the `pynput` library, which the keylogger depends on, is incompatible with the headless (no-GUI) nature of the testing sandbox, causing the implant process to hang.

The `dummy_plugin` successfully verified the entire end-to-end system, including dynamic plugin loading, C2 tasking, and data exfiltration. The `keylogger.py` code is complete and remains the intended initial plugin for deployment in compatible graphical environments.
