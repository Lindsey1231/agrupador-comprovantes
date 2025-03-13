import streamlit as st
import os
from PyPDF2 import PdfMerger

# Função para juntar PDFs
def juntar_pdfs(arquivos):
    merger = PdfMerger()
    
    for arquivo in arquivos:
        merger.append(arquivo)

    caminho_saida = "Comprovante_Agrupado.pdf"
    merger.write(caminho_saida)
    merger.close()
    
    return caminho_saida

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")
    
    if st.button("Juntar PDFs"):
        caminho_pdf_final = juntar_pdfs(uploaded_files)
        
        with open(caminho_pdf_final, "rb") as file:
            st.download_button(
                label="Baixar PDF Agrupado",
                data=file,
                file_name="Comprovante_Agrupado.pdf",
                mime="application/pdf"
            )

