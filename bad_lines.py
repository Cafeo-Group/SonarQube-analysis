import pandas as pd
from io import StringIO

bad_lines = []


def read_csv_with_error_handling(file_path):
    global bad_lines
    temp_df = pd.DataFrame()

    with open(file_path, "r") as f:
        header = f.readline().strip().split(",")
        temp_df = pd.DataFrame(columns=header)

        for i, line in enumerate(f):
            try:
                temp_line_df = pd.read_csv(StringIO(line), header=None)

                if len(temp_line_df.columns) != len(header):
                    print(i + 2)
                    bad_lines.append((i + 2, line.strip()))
                    continue

                temp_line_df.columns = header
                temp_df = pd.concat([temp_df, temp_line_df], ignore_index=True)
            except pd.errors.ParserError:
                print(i + 2)
                bad_lines.append((i + 2, line.strip()))

    bad_lines_df = pd.DataFrame(bad_lines, columns=["Line Number", "Content"])
    bad_lines_df.to_csv("bad_lines.csv", index=False)

    return temp_df


df = read_csv_with_error_handling("commits_report.csv")

print(df.head())
