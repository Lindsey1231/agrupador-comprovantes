import streamlit as st
import os
from PyPDF2 import PdfMerger
import tempfile

def identificar_tipo_arquivo(nome_arquivo):
    """Classifica se o arquivo é um comprovante de pagamento ou um documento (NF, boleto, invoice)"""
    palavras_comprovante = ["PIX", "COMPROVANTE", "TRANSFERENCIA", "PAGAMENTO"]
    
    for palavra in palavras_comprovante:
        if palavra in nome_arquivo.upper():
            return "comprovante"

    return "documento"

def organizar_por_fornecedor(arquivos):
    """Agrupa corretamente os comprovantes de pagamento com suas respectivas NFs, boletos e invoices."""
    agrupados = {}

    for arquivo in arquivos:
        nome = arquivo.name
        tipo = identificar_tipo_arquivo(nome)

        # Extrai a chave de agrupamento a partir do nome do documento oficial (NF, boleto, invoice)
        if tipo == "documento":
            partes = nome.split(" ")
            if len(partes) >= 4:
                chave = " ".join(partes[:4])  # Ex: "(BTG) Pagamento NF 244"
                if chave not in agrupados:
                    agrupados[chave] = {"comprovantes": [], "documentos": []}
                agrupados[chave]["documentos"].append(arquivo)

    # Agora, adicionamos os comprovantes de pagamento ao grupo correto
    for arquivo in arquivos:
        nome = arquivo.name
        tipo = identificar_tipo_arquivo(nome)

        if tipo == "comprovante":
            # Tentamos encontrar a chave correspondente nos documentos já adicionados
            for chave in agrupados:
                if any(part in nome for part in chave.split(" ")):  # Confere se há relação entre os nomes
                    agrupados[chave]["comprovantes"].append(arquivo)
                    break

    pdf_resultados = {}

    for chave, grupos in agrupados.items():
        merger = PdfMerger()

        # Junta primeiro os comprovantes de pagamento, depois os documentos
        for pdf in grupos["comprovantes"] + grupos["documentos"]:
            temp_path = os.path.join(tempfile.gettempdir(), pdf.name)
            with open(temp_path, "wb") as temp_file:
                temp_file.write(pdf.read())
            merger.append(temp_path)

        nome_saida = f"{chave} - Comprovante Completo.pdf"
        caminho_saida = os.path.join(tempfile.gettempdir(), nome_saida)
        merger.write(caminho_saida)
        merger.close()
        pdf_resultados[chave] = caminho_saida

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
