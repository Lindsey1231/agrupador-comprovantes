import streamlit as st
import os
from PyPDF2 import PdfMerger
import tempfile

def identificar_tipo_arquivo(nome_arquivo):
    """Classifica se o arquivo é um comprovante de pagamento ou uma NF/Boleto/Invoice"""
    if any(kw in nome_arquivo.upper() for kw in ["PIX", "COMPROVANTE", "TRANSFERENCIA", "PAGAMENTO"]):
        return "comprovante"
    else:
        return "documento"

def organizar_por_fornecedor(arquivos):
    """Agrupa os arquivos corretamente por fornecedor"""
    agrupados = {}

    for arquivo in arquivos:
        nome = arquivo.name
        tipo = identificar_tipo_arquivo(nome)

        partes = nome.split(" ")
        if len(partes) >= 4:
            chave = " ".join(partes[:4])  # Identificação baseada no padrão de nomeação

            if chave not in agrupados:
                agrupados[chave] = {"comprovantes": [], "documentos": []}

            # Criar arquivo temporário
            temp_path = os.path.join(tempfile.gettempdir(), nome)
            with open(temp_path, "wb") as temp_file:
                temp_file.write(arquivo.read())

            agrupados[chave][tipo + "s"].append(temp_path)

    pdf_resultados = {}

    for chave, grupos in agrupados.items():
        merger = PdfMerger()

        # Primeiro junta os comprovantes de pagamento, depois os documentos
        for pdf_path in grupos["comprovantes"] + grupos["documentos"]:
            merger.append(pdf_path)

        nome_saida = os.path.join(tempfile.gettempdir(), f"{chave} - Comprovante Completo.pdf")
        merger.write(nome_saida)
        merger.close()
        pdf_resultados[chave] = nome_saida

    return pdf_resultados

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")

    if st.button("Juntar PDFs"):
        resultados = organizar_por_fornecedor(uploaded_files)

        for chave, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {chave} - Comprovante Completo.pdf",
                    data=file,
                    file_name=f"{chave} - Comprovante Completo.pdf",
                    mime="application/pdf"
                )
