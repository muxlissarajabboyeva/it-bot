import sqlite3
import csv

conn = sqlite3.connect("terms.db")
cursor = conn.cursor()

with open("terms.csv", newline="", encoding="latin-1") as file:
    reader = csv.DictReader(file, delimiter=';')

    for row in reader:
        cursor.execute("""
        INSERT INTO terms
        (english_word, full_form, uzbek_translation, explanation, example, level)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row["english_word"].strip().lower(),
            row["full_form"].strip(),
            row["uzbek_translation"].strip(),
            row["explanation"].strip(),
            row["example"].strip(),
            row["level"].strip()
        ))

conn.commit()
conn.close()

print("Baza to‘ldirildi 🚀")