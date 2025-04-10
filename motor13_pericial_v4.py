import fitz
import pandas as pd
import re
import os
import sys
import traceback
import PyPDF2
import requests
from motor13_funcoes_auxiliares import (
    extrair_dados_processo,
    extrair_sumario,
    reconstruir_sumario_completo,
    criar_indexador,
    localizar_trct,
    gerar_dados_para_calculo,
    gerar_relatorio,
)

# Configurações da API
API_URL = "https://api.perplexity.ai/chat/completions"
API_KEY = "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"

def chamar_api_perplexity(prompt):
    """
    Função para chamar a API da Perplexity com um prompt fornecido.
    """
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar-pro",  # Modelo atualizado
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        elif response.status_code == 404:
            print("❌ Erro 404: Endpoint ou recurso não encontrado.")
            print("Verifique se o URL da API está correto e se o modelo especificado está disponível.")
        elif response.status_code == 401:
            print("❌ Erro 401: Chave de API inválida ou sem permissões.")
            print("Certifique-se de que sua chave de API está correta.")
        else:
            print(f"❌ Erro na API: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao conectar à API: {e}")
    return None

def motor13(pdf_path):
    """
    Função principal do Motor 13 para processar o PDF e gerar o relatório.
    """
    print("📄 PDF recebido:", pdf_path)
    print("🚀 Iniciando motor 13...")

    # Abrir o documento PDF com fitz (PyMuPDF)
    doc = fitz.open(pdf_path)

    # Extrair dados básicos do processo
    dados_processo = extrair_dados_processo(doc)
    print(f"👤 Reclamante identificado: {dados_processo['Reclamante']}")

    # Extrair sumário e reconstruí-lo
    pagina_sumario, _ = extrair_sumario(doc)
    sumario = reconstruir_sumario_completo(doc, pagina_sumario)
    sumario = criar_indexador(sumario, doc, pagina_sumario)

    # Localizar TRCT no sumário
    dados_trct = localizar_trct(sumario, doc, dados_processo["Reclamante"], pdf_path)

    # Filtrar documentos relevantes no sumário
    palavras_chave = ["sentença", "acórdão", "embargos"]
    sumario["Documento_lower"] = sumario["Documento"].str.lower()
    sumario["Tipo_lower"] = sumario["Tipo"].str.lower()

    filtro_tipo = sumario["Tipo_lower"] == "decisão"
    filtro_doc = sumario.apply(
        lambda row: any(p in row["Documento_lower"] for p in palavras_chave) and row["Documento_lower"] == row["Tipo_lower"],
        axis=1
    )
    
    sumario_filtrado = sumario[filtro_tipo | filtro_doc].copy()

    # Extrair textos das decisões filtradas
    textos = []
    for _, row in sumario_filtrado.iterrows():
        inicio, fim = int(row["Página Inicial"]) - 1, int(row["Página Final"]) - 1
        conteudo = "\n".join([doc[i].get_text() for i in range(inicio, fim + 1)])
        textos.append({"ID": row["ID"], "Tipo": row["Tipo"], "Texto": conteudo})

    # Ler as primeiras páginas do PDF com PyPDF2 para a petição inicial
    reader = PyPDF2.PdfReader(pdf_path)
    texto_inicial = "\n".join([page.extract_text() for page in reader.pages[:10] if page.extract_text()])

    # Carregar o prompt base do arquivo de texto
    if not os.path.exists("prompt_base_motor13.txt"):
        raise FileNotFoundError("O arquivo 'prompt_base_motor13.txt' não foi encontrado.")
    
    with open("prompt_base_motor13.txt", "r", encoding="utf-8") as f:
        prompt_base = f.read()

    # Construir o prompt final para a API
    decisoes_txt = ""
    for t in textos:
        decisoes_txt += f"\n===== {t['Tipo']} (ID {t['ID']}) =====\n{t['Texto']}\n"

    prompt_final = prompt_base + "\n\n" + decisoes_txt + "\n\n===== PETIÇÃO INICIAL =====\n" + texto_inicial

    # Chamar a API da Perplexity com o prompt final
    resposta = chamar_api_perplexity(prompt_final)
    
    if resposta is None:
        raise ValueError("A API não retornou uma resposta válida.")

    # Gerar dados para cálculo e relatório final
    df_resultado = gerar_dados_para_calculo(resposta)
    
    docx = gerar_relatorio(dados_processo, dados_trct, resposta, sumario_filtrado, df_resultado)

    # Salvar o relatório em um arquivo .docx na pasta de saída
    nome_reclamante = dados_processo["Reclamante"].replace(" ", "_").replace("/", "-")
    numero_processo = dados_processo["Número do Processo"].replace(" ", "_").replace("/", "-")
    
    nome_arquivo = f"Relatorio_{nome_reclamante}_{numero_processo}.docx"
    
    if not os.path.exists("output"):
        os.makedirs("output")
    
    caminho_saida = os.path.join("output", nome_arquivo)
    
    docx.save(caminho_saida)
    
    print(f"📁 Relatório salvo em: {caminho_saida}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        caminho_pdf = sys.argv[1]
    else:
        caminho_pdf = "input/processo_completo.pdf"

    try:
        motor13(caminho_pdf)
        print("✅ Execução concluída com sucesso!")
        
    except Exception as e:
        print("❌ ERRO AO EXECUTAR O MOTOR13:")
        traceback.print_exc()
