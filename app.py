from flask import Flask, render_template, request, send_from_directory
import os
import subprocess

app = Flask(__name__)

UPLOAD_FOLDER = "input"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", status=None, relatorio_disponivel=False)

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files["pdf_file"]
    filename = "processo_completo.pdf"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        subprocess.run(["python", "motor13_pericial_v4.py", filepath], check=True)
    except subprocess.CalledProcessError:
        return render_template("index.html", status="❌ Erro ao gerar relatório.", relatorio_disponivel=False)

    for f in os.listdir(OUTPUT_FOLDER):
        if f.lower().endswith(".docx"):
            return render_template("index.html", status="✅ Relatório gerado com sucesso!", relatorio_disponivel=True, nome_arquivo=f)

    return render_template("index.html", status="❌ Relatório não encontrado.", relatorio_disponivel=False)

@app.route("/download/<nome_arquivo>")
def baixar_relatorio(nome_arquivo):
    return send_from_directory(OUTPUT_FOLDER, nome_arquivo, as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

