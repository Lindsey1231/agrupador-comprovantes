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
            chave = " ".join(partes[:4])  # Usa os 4 primeiros elementos para garantir a separação correta
            if chave not in agrupados:
                agrupados[chave] = []
            agrupados[chave].append(arquivo)
        elif any(kw in nome.upper() for kw in ["PIX", "COMPROVANTE", "PAGAMENTO", "TRANSFERENCIA"]):
            # Associar comprovante ao fornecedor correto
            for chave in agrupados:
                if chave in nome:
                    agrupados[chave].insert(0, arquivo)  # Insere o comprovante primeiro
                    break
    
    pdf_resultados = {}
    
    for chave, lista_arquivos in agrupados.items():
        if len(lista_arquivos) > 1:  # Só junta se houver um comprovante + NF/boletos/invoice
            merger = PdfMerger()
            temp_files = []
            
            for pdf in lista_arquivos:
                temp_path = os.path.join(tempfile.gettempdir(), pdf.name)
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(pdf.getbuffer())  # Corrige a leitura dos arquivos do Streamlit
                temp_files.append(temp_path)
                merger.append(temp_path)
            
            caminho_saida = os.path.join(tempfile.gettempdir(), f"{chave} - Comprovante Completo.pdf")
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
