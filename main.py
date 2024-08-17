import pandas as pd
import requests
import os
from pydriller import Repository

# import the csv with code samples to be used as dataframe

samples_df = pd.read_csv('samples.csv', delimiter=';', header=None, names=['sample_name', 'github_address'])

# Print the columns of the DataFrame to debug
print(samples_df.columns)

# set the path to the csv file

# create the helper function to read the csv file and return sample name and github address

def get_sample():
    for index, row in samples_df.iterrows():
        yield row['sample_name'], row['github_address']


# create the helper function to create the Sonarqube project with the sample name with login credentials
def create_sonarqube_project(sample_name):
    url = 'http://localhost:9000/api/projects/create'
    data = {
        'name': sample_name,
        'project': sample_name
    }
    response = requests.post(url, data=data, auth=('admin', 'root'))
    print(response.text)
    return response


# create the helper function to clone the GitHub repository and cd to the repository
def clone_repository(github_address):
    os.system(f'git clone {github_address}')


# create the helper function to checkout to specific commit
def checkout_commit(commit):
    os.system(f'git checkout {commit}')


# create the sonar-scanner configuration file
def create_sonar_scanner_config(sample_name):
    with open('sonar-project.properties', 'w') as f:
        f.write(
            f'sonar.projectKey={sample_name}\nsonar.sources=.\nsonar.host.url=http://localhost:9000\nsonar.token=sqa_8b5b36d0d8f38e528b7e7535a2708229f50fbc21')


# create the helper function to run the sonar-scanner
def run_sonar_scanner():
    os.system('sonar-scanner')


# create the helper function to delete the repository from local machine
def delete_repository(repository_name):
    os.system(f'rm -rf {repository_name}')


# create the helper function to extract the issues from the Sonarqube project to a csv file
def extract_issues(sample_name):
    url = f'http://localhost:9000/api/issues/search?componentKeys={sample_name}'
    response = requests.get(url, auth=('admin', 'root'))
    issues = response.json()['issues']
    issues_df = pd.DataFrame(issues)
    issues_df.to_csv(f'issues/{sample_name}_issues.csv')

# create the helper function to extract the code snippets based on the issues from the Sonarqube project to a csv file to a csv file
def extract_code_snippets(sample_name):
    # issues_df = pd.read_csv(f'issues/{sample_name}_issues.csv')
    pass


# create the function to run the Git part (create SonarQube project, clone, checkout, run sonar-scanner, delete repository)
def run_git_part():
    sliced_samples_df = samples_df.tail(50)
    for index, row in sliced_samples_df.iterrows():
        sample_name, github_address = row['sample_name'], row['github_address']
        # create_sonarqube_project(sample_name)
        print(f'Running SonarQube for {sample_name}')
        clone_repository(github_address)
        repository_name = github_address.split('/')[-1].replace('.git', '')
        os.chdir(repository_name)
        current_path = os.getcwd()

        # run only for the first and last commit of the repository
        commits = list(Repository(current_path).traverse_commits())
        #keep only the first and last commit on the list
        first_commit = commits[0]
        last_commit = commits[-1]
        commits_to_checkout = [first_commit, last_commit]
        print(f'First commit: {first_commit.hash}')
        print(f'Last commit: {last_commit.hash}')

        for commit in commits_to_checkout:
            checkout_commit(commit.hash)
            print(f'Running SonarQube for commit: {commit.hash}')
            create_sonar_scanner_config(sample_name)
            run_sonar_scanner()
            os.system('git clean -fd')

        os.chdir('..')
        print(f'Deleting repository: {repository_name}')
        delete_repository(repository_name)



# create then function to run the SonarQube part (extract issues, extract code snippets)
def run_sonarqube_part():
    for sample_name in get_sample():
        extract_issues(sample_name)
        extract_code_snippets(sample_name)

# create the main function to run the Git part and SonarQube part
def main():
    run_git_part()

if __name__ == "__main__":
    main()
