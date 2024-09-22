import click
import requests
import os
from cryptography.fernet import Fernet
import json

API_URL = "http://localhost:8000"  # Replace with your actual API URL

def get_or_create_config(project_name=None):
    config_file = "dotenvpull_config.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
    else:
        config = {}

    if project_name:
        if project_name not in config:
            encryption_key = Fernet.generate_key()
            config[project_name] = {
                "encryption_key": encryption_key.decode(),
                "access_key": None
            }
            with open(config_file, "w") as f:
                json.dump(config, f)
        return config[project_name]
    else:
        return config

def update_config(project_name, access_key):
    config = get_or_create_config()
    config[project_name]["access_key"] = access_key
    with open("dotenvpull_config.json", "w") as f:
        json.dump(config, f)

@click.group()
def cli():
    pass

@cli.command()
@click.argument('project_name')
@click.argument('file_path')
def push(project_name, file_path):
    """Push a .env or config file to the server"""
    if not os.path.exists(file_path):
        click.echo("Error: File not found")
        return

    project_config = get_or_create_config(project_name)
    fernet = Fernet(project_config["encryption_key"].encode())

    with open(file_path, "rb") as f:
        content = f.read()

    encrypted_content = fernet.encrypt(content)

    headers = {}
    if project_config["access_key"]:
        headers["X-API-Key"] = project_config["access_key"]

    response = requests.post(f"{API_URL}/store", json={
        "project_id": project_name,
        "encrypted_content": encrypted_content.decode()
    }, headers=headers)

    if response.status_code == 200:
        result = response.json()
        if "access_key" in result:
            update_config(project_name, result["access_key"])
            click.echo("New access key generated and stored")
        click.echo("File pushed successfully")
    else:
        click.echo(f"Error: {response.json()['detail']}")

@cli.command()
@click.argument('project_name')
@click.argument('output_file')
@click.option('--force', is_flag=True, help="Overwrite the output file if it already exists")
def pull(project_name, output_file, force):
    """Pull a .env or config file from the server"""
    if os.path.exists(output_file) and not force:
        click.echo("Error: Output file already exists. Use --force to overwrite.")
        return

    project_config = get_or_create_config(project_name)
    if not project_config["access_key"]:
        click.echo("Error: No access key found. Please push data first.")
        return

    fernet = Fernet(project_config["encryption_key"].encode())

    headers = {"X-API-Key": project_config["access_key"]}
    response = requests.get(f"{API_URL}/retrieve", headers=headers)

    if response.status_code == 200:
        encrypted_content = response.json()['encrypted_content']
        decrypted_content = fernet.decrypt(encrypted_content.encode())

        with open(output_file, "wb") as f:
            f.write(decrypted_content)

        click.echo(f"File pulled successfully and saved to {output_file}")
    else:
        click.echo(f"Error: {response.json()['detail']}")

@cli.command()
@click.argument('project_name')
@click.argument('file_path')
def update(project_name, file_path):
    """Update an existing .env or config file on the server"""
    project_config = get_or_create_config(project_name)
    if not project_config["access_key"]:
        click.echo("Error: No access key found. Please push data first.")
        return

    fernet = Fernet(project_config["encryption_key"].encode())

    with open(file_path, "rb") as f:
        content = f.read()

    encrypted_content = fernet.encrypt(content)

    headers = {"X-API-Key": project_config["access_key"]}
    response = requests.put(f"{API_URL}/update", json={
        "project_id": project_name,
        "encrypted_content": encrypted_content.decode()
    }, headers=headers)

    if response.status_code == 200:
        click.echo("File updated successfully")
    else:
        click.echo(f"Error: {response.json()['detail']}")

@cli.command()
@click.argument('project_name')
def delete(project_name):
    """Delete a .env or config file from the server"""
    project_config = get_or_create_config(project_name)
    if not project_config["access_key"]:
        click.echo("Error: No access key found. Cannot delete.")
        return

    headers = {"X-API-Key": project_config["access_key"]}
    response = requests.delete(f"{API_URL}/delete", headers=headers)

    if response.status_code == 200:
        click.echo("File deleted successfully")
        config = get_or_create_config()
        del config[project_name]
        with open("dotenvpull_config.json", "w") as f:
            json.dump(config, f)
        click.echo(f"Project '{project_name}' removed from local config")
    else:
        click.echo(f"Error: {response.json()['detail']}")

@cli.command()
def list_projects():
    """List all projects in the local config"""
    config = get_or_create_config()
    if config:
        click.echo("Projects in local config:")
        for project in config.keys():
            click.echo(f"- {project}")
    else:
        click.echo("No projects found in local config")

if __name__ == '__main__':
    cli()