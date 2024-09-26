import glob
from multiprocessing import Pool
from os import makedirs

import pandas as pd
import requests
import os
import subprocess
import time
import csv
from requests.exceptions import JSONDecodeError


SONAR_URL = ""
SONAR_LOGIN = ""
SONAR_PASSWORD = ""
COMMITS_REPORT_FILE = "../../commits_report.csv"


samples_df = pd.read_csv(
    "samples.csv",
    delimiter=";",
    header=None,
    names=["sample_name", "github_address"],
)

script_dir = os.path.dirname(os.path.abspath(__file__))
samples_folder = os.path.join(script_dir, "samples")


def run_shell_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_commit_date(commit_hash):
    return run_shell_command(f"git show -s --format=%ci {commit_hash} | cut -d' ' -f1")


def get_main_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            main_branch = result.stdout.strip()
            return main_branch
        else:
            print("Erro ao tentar obter a branch principal:", result.stderr)
            return None
    except Exception as e:
        print(f"Erro: {e}")
        return None


def create_sonarqube_project(sample_name):
    print(f"Creating SonarQube project for {sample_name}")

    url = f"{SONAR_URL}/api/projects/create"
    data = {"name": f"{sample_name}", "project": f"{sample_name}"}
    response = requests.post(url, data=data, auth=(SONAR_LOGIN, SONAR_PASSWORD))
    print(response.text)
    return response


def clone_repository(github_address):
    os.system(
        f'git clone {github_address} {samples_folder}/{github_address.split("/")[-1].replace(".git", "")}'
    )


def git_checkout(commit_hash):
    print(f"Checkout to {commit_hash}")
    result = run_shell_command(f"git checkout {commit_hash}")
    if "error" in result.lower():
        print(f"Erro ao realizar checkout para o commit {commit_hash}")
        return False
    return True


def create_sonar_scanner_config(sample_name, token):
    print(f"Creating sonar-scanner configuration file for {sample_name}")
    with open("sonar-project.properties", "w") as f:
        f.write(
            f"sonar.projectKey={sample_name}\nsonar.sources=.\nsonar.host.url={SONAR_URL}\nsonar.token={token}"
        )


def run_sonar_scanner(commit_hash, commit_date, project_key, token):
    result = run_shell_command(
        f"sonar-scanner -Dsonar.projectKey={project_key} "
        f"-Dsonar.sources=. -Dsonar.host.url={SONAR_URL} "
        f"-Dsonar.token={token} "
        f"-Dsonar.projectVersion={commit_hash} "
        f"-Dsonar.projectDate={commit_date}"
    )

    if "error" in result.lower():
        print(f"Erro ao executar o sonar-scanner para o commit {commit_hash}")
        print(result)


def get_issues_detected(project_key, token):
    print(f"Getting issues for project {project_key} - {token}")
    url = f"{SONAR_URL}/api/issues/search?components={project_key}&s=FILE_LINE&issueStatuses=ACCEPTED,CONFIRMED,FALSE_POSITIVE,FIXED,OPEN&ps=500&facets=cleanCodeAttributeCategories,impactSoftwareQualities,codeVariants&additionalFields=_all&timeZone=America/Sao_Paulo"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        issues = response.json()
        return issues
    except JSONDecodeError as e:
        print(f"Erro ao decodificar a resposta JSON: {e}")
        return None
    except requests.RequestException as e:
        print(f"Erro na requisição HTTP: {e}")
        return None


def generate_sonarqube_token(project_key):
    print(f"Generating token for project {project_key}")

    token_name = f"token_{project_key}"

    url_list = f"{SONAR_URL}/api/user_tokens/search"
    response_list = requests.get(url_list, auth=(SONAR_LOGIN, SONAR_PASSWORD))

    if response_list.status_code == 200:
        existing_tokens = response_list.json().get("userTokens", [])

        for token in existing_tokens:
            if token["name"] == token_name:
                print(f"Token '{token_name}' já existe. Excluindo o token antigo...")

                url_revoke = f"{SONAR_URL}/api/user_tokens/revoke"
                data_revoke = {"name": token_name}
                response_revoke = requests.post(
                    url_revoke, data=data_revoke, auth=(SONAR_LOGIN, SONAR_PASSWORD)
                )

                if response_revoke.status_code == 204:
                    print(f"Token '{token_name}' excluído com sucesso.")
                else:
                    print(f"Falha ao excluir o token: {response_revoke.text}")
                    return None

        url_generate = f"{SONAR_URL}/api/user_tokens/generate"
        data = {"name": token_name, "login": SONAR_LOGIN}
        response_generate = requests.post(
            url_generate, data=data, auth=(SONAR_LOGIN, SONAR_PASSWORD)
        )

        if response_generate.status_code == 200:
            token = response_generate.json().get("token")
            print(f"Token generated: {token}")
            return token
        else:
            print(f"Failed to generate token: {response_generate.text}")
            return None
    else:
        print(f"Failed to retrieve existing tokens: {response_list.text}")
        return None


def delete_repository(repository_name):
    os.system(f"rm -rf {repository_name}")


def extract_issues(sample_name):
    os.makedirs("data/issues", exist_ok=True)

    url = f"http://localhost:9000/api/issues/search?componentKeys={sample_name}&ps=500"
    response = requests.get(url, auth=("admin", "root"))
    total_issues = int(response.json().get("total", 0))

    if total_issues <= 500:
        print(f"Total issues: {total_issues}")
        print(f"Extracting issues for single page")
        current_issues = response.json().get("issues", [])
        current_df = pd.DataFrame(current_issues)
        current_df.to_csv(f"data/issues/{sample_name}_issues.csv")
    elif 500 <= total_issues <= 10000:
        total_pages = (total_issues // 500) + 1
        for page in range(1, total_pages + 1):
            print(f"Extracting issues for page {page}")
            paged_url = url + f"&p={page}"
            response = requests.get(paged_url, auth=("admin", "root"))
            issues = response.json().get("issues", [])
            issues_df = pd.DataFrame(issues)
            issues_df.to_csv(f"data/issues/{sample_name}_{page}_issues.csv")
    else:
        impact_software_qualities = ("MAINTAINABILITY", "RELIABILITY", "SECURITY")
        for quality in impact_software_qualities:
            quality_url = f"{url}&impactSoftwareQualities={quality}"
            response = requests.get(quality_url, auth=("admin", "root"))
            total_quality_issues = int(response.json().get("total", 0))
            if total_quality_issues <= 500:
                print(f"Total issues for {quality}: {total_quality_issues}")
                print(f"Extracting issues for single page")
                current_issues = response.json().get("issues", [])
                current_df = pd.DataFrame(current_issues)
                current_df.to_csv(f"data/issues/{sample_name}_{quality}_issues.csv")
            elif 500 <= total_quality_issues <= 10000:
                total_pages = (total_issues // 500) + 1
                for page in range(1, total_pages + 1):
                    print(f"Extracting {quality} issues for page {page}")
                    paged_url = quality_url + f"&p={page}"
                    response = requests.get(paged_url, auth=("admin", "root"))
                    issues = response.json().get("issues", [])
                    issues_df = pd.DataFrame(issues)
                    issues_df.to_csv(
                        f"data/issues/{sample_name}_{quality}_{page}_issues.csv"
                    )
            else:
                print(f"Total issues for {quality} is greater than 10000")


def analyze_commits(sample_name, token):
    print(f"Analyzing commits for {sample_name}")

    commits = run_shell_command("git rev-list --all --reverse").splitlines()
    count = 0
    num_commits = len(commits)
    print("Number of commits:", num_commits)

    with open(COMMITS_REPORT_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Sample", "Commit Hash", "Date", "Analysis Date", "Issues"])

        for commit_hash in commits:
            try:

                git_checkout(commit_hash)

                count += 1
                print(f"Analyzing commit {count}/{num_commits} {commit_hash}...")

                commit_date = get_commit_date(commit_hash)
                print(f"Commit date: {commit_date}")

                run_sonar_scanner(commit_hash, commit_date, sample_name, token)

                print("Waiting for SonarQube to process analysis...")
                time.sleep(15)

                issues_detected = get_issues_detected(sample_name, token)
                current_date = time.strftime("%Y-%m-%d %H:%M:%S")

                writer.writerow(
                    [
                        sample_name,
                        commit_hash,
                        commit_date,
                        current_date,
                        issues_detected,
                    ]
                )
            except Exception as e:
                print(f"Erro ao analisar o commit {commit_hash}: {str(e)}")


def run_git_part(row):
    sample_name, github_address = row["sample_name"], row["github_address"]
    create_sonarqube_project(sample_name)
    token = generate_sonarqube_token(sample_name)
    print(f"Running SonarQube git clone for {sample_name}")
    clone_repository(github_address)
    repository_name = github_address.split("/")[-1].replace(".git", "")
    os.chdir(f"{samples_folder}/{repository_name}")
    print(f"cd  {samples_folder}/{repository_name}")
    create_sonar_scanner_config(sample_name, token)

    analyze_commits(sample_name, token)

    os.chdir(samples_folder)
    print(f"Deleting repository directory: {samples_folder}/{repository_name}")
    delete_repository(f"{samples_folder}/{repository_name}")


def run_sonarqube_issues_part():
    for index, row in samples_df.iterrows():
        sample_name = row["sample_name"]
        print(f"Extracting issues for {sample_name}")
        extract_issues(sample_name)

    issues_list = []
    for file_path in glob.glob("data/issues/*_issues.csv"):
        if os.path.exists(file_path):
            issues_list.append(pd.read_csv(file_path))
        else:
            print(f"File not found: {file_path}")

    if issues_list:
        issues_df = pd.concat(issues_list, ignore_index=True)
        issues_df.drop_duplicates(subset="key", inplace=True)
        issues_df.to_csv("data/issues/0all.csv", index=False)
    else:
        print("No issues files to merge.")


def run_sonarqube_snippets_part():

    issues_df = pd.read_csv("data/issues/0all_nondup.csv")

    num_threads = 124
    print(f"Number of threads: {num_threads}")

    #

    print("Merging all code snippets into one csv file")
    snippets_list = []

    for issue_key in issues_df["key"]:
        try:
            snippets_df = pd.read_csv(
                f"data/code_snippets/{issue_key}_code_snippets.csv"
            )
            snippets_list.append(snippets_df)
        except Exception as e:
            print(f"Error processing {issue_key}: {e}")
            continue

    if snippets_list:
        merged_snippets_df = pd.concat(snippets_list, ignore_index=True)
        merged_snippets_df.to_csv(
            "data/code_snippets/0all_code_snippets.csv", index=False
        )
    else:
        print("No code snippets to merge.")


def main():
    print("start at", time.strftime("%Y-%m-%d %H:%M:%S"))
    num_cores = os.cpu_count()
    print(f"Number of cores: {num_cores}")
    with Pool(processes=num_cores) as pool:
        pool.map(run_git_part, [row for _, row in samples_df.iterrows()])
    print("end at", time.strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
