from multiprocessing import Pool
import pandas as pd
import requests
import os
import subprocess
import time
import csv
from requests.exceptions import JSONDecodeError
import glob


SONAR_URL = ""
SONAR_LOGIN = ""
SONAR_PASSWORD = ""
COMMITS_REPORT_FILE = "../../results/commits_report_java.csv"


samples_df = pd.read_csv(
    "samplesJava1.csv",
    delimiter=";",
    header=None,
    names=["sample_name", "github_address"],
)

script_dir = os.path.dirname(os.path.abspath(__file__))
samples_folder = os.path.join(script_dir, "samples")


def run_shell_command(command, cwd=None):
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, cwd=cwd
    )
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


def find_file(directory, file_name):
    for root, dirs, files in os.walk(directory):
        if file_name in files:
            return root
    return None


def create_sonar_scanner_config(sample_name, token, binaries_path="target/classes"):
    print(f"Creating sonar-scanner configuration file for {sample_name}")
    with open("sonar-project.properties", "w") as f:
        f.write(
            f"sonar.projectKey={sample_name}\n"
            f"sonar.sources=.\n"
            f"sonar.host.url={SONAR_URL}\n"
            f"sonar.token={token}\n"
            f"sonar.java.binaries={binaries_path}\n"  # Adiciona o caminho das classes compiladas
        )


def ensure_sonar_plugin_in_gradle_groovy():
    """Verifica e adiciona o plugin SonarQube ao build.gradle, se necessário"""
    gradle_groovy_file = "build.gradle"
    sonar_plugin = 'id "org.sonarqube" version "5.1.0.4882"'

    # Lê o conteúdo do arquivo
    with open(gradle_groovy_file, "r") as file:
        content = file.read()

    # Verifica se o plugin já está presente no build.gradle
    if sonar_plugin not in content:
        print("Adicionando o plugin SonarQube ao build.gradle...")

        # Verifica se já existe um bloco de plugins
        if "plugins {" in content:
            # Adiciona o plugin SonarQube no bloco de plugins existente
            content = content.replace("plugins {", f"plugins {{\n    {sonar_plugin}\n")
        else:
            # Cria o bloco de plugins e adiciona o plugin SonarQube
            content = f"plugins {{\n    {sonar_plugin}\n}}\n\n" + content

        # Salva as alterações no arquivo
        with open(gradle_groovy_file, "w") as file:
            file.write(content)

        print("Plugin SonarQube adicionado.")
    else:
        print("Plugin SonarQube já está presente no build.gradle.")


def ensure_sonar_plugin_in_gradle_kotlin():
    """Verifica e adiciona o plugin SonarQube ao build.gradle.kts, se necessário"""
    gradle_kotlin_file = "build.gradle.kts"
    sonar_plugin = 'id("org.sonarqube") version "5.1.0.4882"'

    # Lê o conteúdo do arquivo
    with open(gradle_kotlin_file, "r") as file:
        content = file.read()

    # Verifica se o plugin já está presente no build.gradle.kts
    if sonar_plugin not in content:
        print("Adicionando o plugin SonarQube ao build.gradle.kts...")

        # Verifica se já existe um bloco de plugins
        if "plugins {" in content:
            # Adiciona o plugin SonarQube no bloco de plugins existente
            content = content.replace("plugins {", f"plugins {{\n    {sonar_plugin}\n")
        else:
            # Cria o bloco de plugins e adiciona o plugin SonarQube
            content = f"plugins {{\n    {sonar_plugin}\n}}\n\n" + content

        # Salva as alterações no arquivo
        with open(gradle_kotlin_file, "w") as file:
            file.write(content)

        print("Plugin SonarQube adicionado.")
    else:
        print("Plugin SonarQube já está presente no build.gradle.kts.")


def ensure_sonar_plugin_in_maven():
    """Verifica e adiciona a configuração do plugin SonarQube ao pom.xml e o caminho das classes compiladas se necessário."""
    maven_files = glob.glob(
        "**/pom.xml", recursive=True
    )  # Procura pom.xml em subdiretórios

    sonar_plugin_config = """
    <plugin>
        <groupId>org.sonarsource.scanner.maven</groupId>
        <artifactId>sonar-maven-plugin</artifactId>
        <version>3.9.0.2155</version>
    </plugin>
    """

    compiler_plugin_config = """
    <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.8.1</version>
        <configuration>
            <source>11</source>
            <target>11</target>
        </configuration>
    </plugin>
    """

    # Caminho para as classes compiladas (ajuste conforme necessário)
    compiled_classes_path = "target/classes"

    for maven_file in maven_files:
        with open(maven_file, "r") as file:
            content = file.read()

        # Verifica e adiciona o plugin SonarQube se necessário
        if sonar_plugin_config.strip() not in content:
            print(f"Adicionando a configuração do plugin SonarQube ao {maven_file}...")
            content = content.replace(
                "<plugins>", "<plugins>\n        " + sonar_plugin_config.strip() + "\n"
            )
            with open(maven_file, "w") as file:
                file.write(content)
            print(f"Plugin SonarQube adicionado ao {maven_file}.")
        else:
            print(f"Plugin SonarQube já está presente no {maven_file}.")

        # Verifica e adiciona o maven-compiler-plugin se necessário
        if compiler_plugin_config.strip() not in content:
            print(f"Adicionando o maven-compiler-plugin ao {maven_file}...")
            if "<plugins>" in content:
                content = content.replace(
                    "<plugins>",
                    "<plugins>\n        " + compiler_plugin_config.strip() + "\n",
                )
            else:
                content = content.replace(
                    "</build>",
                    "\n    <plugins>\n        "
                    + compiler_plugin_config.strip()
                    + "\n    </plugins>\n</build>",
                )
            with open(maven_file, "w") as file:
                file.write(content)
            print(f"maven-compiler-plugin adicionado ao {maven_file}.")
        else:
            print(f"maven-compiler-plugin já está presente no {maven_file}.")

        # Verifica e adiciona o caminho das classes compiladas se necessário
        if (
            os.path.exists(compiled_classes_path)
            and "<properties>" in content
            and "sonar.java.binaries" not in content
        ):
            print(f"Adicionando o caminho das classes compiladas ao {maven_file}...")
            properties_start = content.index("<properties>") + len("<properties>")
            content = (
                content[:properties_start]
                + f"\n        <sonar.java.binaries>{compiled_classes_path}</sonar.java.binaries>"
                + content[properties_start:]
            )
            with open(maven_file, "w") as file:
                file.write(content)
            print(f"Caminho das classes compiladas adicionado ao {maven_file}.")
        elif "sonar.java.binaries" in content:
            print(f"Caminho das classes compiladas já está presente no {maven_file}.")
        else:
            print(
                f"O diretório {compiled_classes_path} não existe. Verifique a compilação."
            )


def run_sonar_scanner(commit_hash, commit_date, project_key, token):
    project_root = os.getcwd()
    maven_files = glob.glob("**/pom.xml", recursive=True)
    gradle_groovy_file = "build.gradle"
    gradle_kotlin_file = "build.gradle.kts"

    if maven_files:
        print("SonarScanner for Maven")
        ensure_sonar_plugin_in_maven()

        for maven_file in maven_files:
            project_root = os.path.dirname(maven_file)  # Diretório do pom.xml
            print(f"Compilando o projeto {project_key} no diretório: {project_root}")
            run_shell_command("mvn clean compile", cwd=project_root)
            print(f"Executando SonarScanner no diretório: {project_root}")
            result = run_shell_command(
                f"mvn sonar:sonar -Dsonar.projectKey={project_key} "
                f"-Dsonar.host.url={SONAR_URL} "
                f"-Dsonar.token={token} "
                f"-Dsonar.projectVersion={commit_hash} "
                f"-Dsonar.projectDate={commit_date} ",
                # f"-Dsonar.java.binaries=target/classes",
                cwd=project_root,  # Define o diretório de trabalho
            )

            if result != 0:
                print(
                    f"Erro ao executar SonarScanner em {project_root}, código de retorno: {result}"
                )
            else:
                print(f"SonarScanner executado com sucesso em {project_root}.")
    elif find_file(project_root, gradle_groovy_file):
        print("SonarScanner for Gradle (Groovy)")
        ensure_sonar_plugin_in_gradle_groovy()
        result = run_shell_command(
            f"./gradlew sonarqube -Dsonar.projectKey={project_key} "
            f"-Dsonar.host.url={SONAR_URL} "
            f"-Dsonar.token={token} "
            f"-Dsonar.projectVersion={commit_hash} "
            f"-Dsonar.projectDate={commit_date}"
        )
    elif find_file(project_root, gradle_kotlin_file):
        print("SonarScanner for Gradle (Kotlin)")
        ensure_sonar_plugin_in_gradle_kotlin()
        result = run_shell_command(
            f"./gradlew sonarqube -Dsonar.projectKey={project_key} "
            f"-Dsonar.host.url={SONAR_URL} "
            f"-Dsonar.token={token} "
            f"-Dsonar.projectVersion={commit_hash} "
            f"-Dsonar.projectDate={commit_date}"
        )
    else:
        print("SonarScanner for unknown build tool.")
        result = run_shell_command(
            f"sonar-scanner -Dsonar.projectKey={project_key} "
            f"-Dsonar.sources=. -Dsonar.host.url={SONAR_URL} "
            f"-Dsonar.token={token} "
            f"-Dsonar.projectVersion={commit_hash} "
            f"-Dsonar.projectDate={commit_date}"
        )
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
                print(
                    f"Analyzing commit - {sample_name} - {count}/{num_commits} - {commit_hash}..."
                )

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


def main():
    start_time = time.time()
    print("start at", time.strftime("%Y-%m-%d %H:%M:%S"))
    num_cores = os.cpu_count()
    print(f"Number of cores: {num_cores}")
    with Pool(processes=num_cores) as pool:
        pool.map(run_git_part, [row for _, row in samples_df.iterrows()])
    print("end at", time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Total time: {time.time() - start_time}")


if __name__ == "__main__":
    main()
