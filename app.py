import streamlit as st
import os
from PyPDF2 import PdfMerger
import tempfile

def organizar_por_fornecedor(arquivos):
    agrupados = {}

    for arquivo in arquivos:
        nome = arquivo.name
        partes = nome.split(" ")

        if any(kw in nome.upper() for kw in ["NF", "BOLETO", "INVOICE"]):
            chave = " ".join(partes[:4])  # Usa os 4 primeiros elementos para separar
            if chave not in agrupados:
                agrupados[chave] = []
            agrupados[chave].append(arquivo)
        elif any(kw in nome.upper() for kw in ["PIX", "COMPROVANTE", "PAGAMENTO", "TRANSFERENCIA"]):
            for chave in agrupados:
                if chave in nome:
                    agrupados[chave].insert(0, arquivo)  # Insere o comprovante primeiro
                    break

    pdf_resultados = {}

    for chave, lista_arquivos in agrupados.items():
        if len(lista_arquivos) > 1:  
            merger = PdfMerger()
            temp_files = []

            try:
                for pdf in lista_arquivos:
                    temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                    with open(temp_path, "wb") as temp_file:
                        temp_file.write(pdf.getbuffer())  
                    temp_files.append(temp_path)
                    merger.append(temp_path)

                caminho_saida = os.path.join(tempfile.gettempdir(), f"{chave} - Comprovante Completo.pdf")
                merger.write(caminho_saida)
                merger.close()
                pdf_resultados[chave] = caminho_saida
            except Exception as e:
                st.error(f"Erro ao processar {chave}: {e}")
    
    return pdf_resultados

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")

    if st.button("Juntar PDFs"):
        st.write("🔄 Processando arquivos... Aguarde.")
        resultados = organizar_por_fornecedor(uploaded_files)

        if not resultados:
            st.error("Nenhum arquivo foi processado. Verifique os nomes e tente novamente.")

        for chave, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {chave} - Comprovante Completo.pdf",
                    data=file,
                    file_name=f"{chave} - Comprovante Completo.pdf",
                    mime="application/pdf"
                )
