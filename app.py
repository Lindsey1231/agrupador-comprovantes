import streamlit as st
import os
from PyPDF2 import PdfMerger

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    
    for arquivo in arquivos:
        nome = arquivo.name
        partes = nome.split(" ")
        
        if len(partes) >= 4:
            chave = " ".join(partes[:4])  # Pega até o número da NF, boleto ou invoice
            
            if chave not in agrupados:
                agrupados[chave] = []
            
            agrupados[chave].append(arquivo)
    
    pdf_resultados = {}
    
    for chave, lista_arquivos in agrupados.items():
        merger = PdfMerger()
        for pdf in lista_arquivos:
            merger.append(pdf)
        
        nome_saida = f"{chave} - Comprovante Completo.pdf"
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
                    label=f"Baixar {resultado}",
                    data=file,
                    file_name=resultado,
                    mime="application/pdf"
                )

