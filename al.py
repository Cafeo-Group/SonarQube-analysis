import pandas as pd


def identificar_linhas_iguais(csv_path, colunas_chave):
    # Ler o CSV
    df = pd.read_csv(csv_path)
    # print(len(df))

    duplicadas = df[df.duplicated(subset=colunas_chave, keep=False)]

    resultados = []

    for _, grupo in duplicadas.groupby(colunas_chave):
        diferentes = {
            col: grupo[col].unique().tolist()
            for col in grupo.columns
            if col != "sample"
        }

        resultados.append(diferentes)

    return resultados


def identificar_valores_unicos_sample(csv_path):
    df = pd.read_csv(csv_path)

    if "sample" not in df.columns:
        raise ValueError("A coluna 'sample' não foi encontrada no arquivo CSV.")

    valores_unicos = df["sample"].unique()

    print(len(valores_unicos))

    return valores_unicos


csv_path = "results/commits_report_analysis_total.csv"
colunas_chave = [
    "key",
]
resultados = identificar_linhas_iguais(csv_path, colunas_chave)

for i, res in enumerate(resultados, 1):
    print(f"Duplicado {i}:")
    for coluna, valores in res.items():
        print(f" - {coluna}: {valores}")


valores_unicos_sample = identificar_valores_unicos_sample(csv_path)

print("Valores únicos na coluna 'sample':", valores_unicos_sample)
