import streamlit as st
import os
from PyPDF2 import PdfMerger
import tempfile

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    
    for arquivo in arquivos:
        nome = arquivo.name
        if any(kw in nome.upper() for kw in ["NF", "BOLETO", "INVOICE"]):
            chave = nome  # O nome do arquivo de NF, boleto ou invoice será usado para nomear o PDF final
            if chave not in agrupados:
                agrupados[chave] = []
            agrupados[chave].append(arquivo)
        elif any(kw in nome.upper() for kw in ["PIX", "COMPROVANTE", "PAGAMENTO", "TRANSFERENCIA"]):
            # Se for um comprovante de pagamento, associamos à NF correspondente
            for chave in agrupados:
                fornecedor_nome = " ".join(chave.split(" ")[3:])  # Obtém o nome do fornecedor
                if fornecedor_nome in nome:
                    agrupados[chave].insert(0, arquivo)  # Insere o comprovante primeiro no grupo
                    break
    
    pdf_resultados = {}
    
    for chave, lista_arquivos in agrupados.items():
        merger = PdfMerger()
        temp_files = []
        
        for pdf in lista_arquivos:
            temp_path = os.path.join(tempfile.gettempdir(), pdf.name)
            with open(temp_path, "wb") as temp_file:
                temp_file.write(pdf.read())
            temp_files.append(temp_path)
            merger.append(temp_path)
        
        caminho_saida = os.path.join(tempfile.gettempdir(), chave)
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
                    label=f"Baixar {chave}",
                    data=file,
                    file_name=chave,
                    mime="application/pdf"
                )
