import streamlit as st
import os
import tempfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar o nome do fornecedor."""
    try:
        reader = PdfReader(arquivo)
        texto = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return texto.lower()
    except:
        return ""

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    st.write("### Arquivos detectados:")
    
    # Primeiro, identificamos as NFs, boletos ou invoices
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        
        if nome.startswith("(BTG)" ) or nome.startswith("(INTER)") or nome.startswith("(BV)"):
            fornecedor_nome = " ".join(texto_pdf.split()[:5])  # Captura as primeiras palavras do texto
            if fornecedor_nome:
                agrupados[fornecedor_nome] = {"nf": arquivo, "comprovante": None}
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL para {fornecedor_nome}")
    
    # Agora, associamos os comprovantes de pagamento
    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        
        if nome.upper().startswith("PIX"):
            for fornecedor, docs in agrupados.items():
                if fornecedor in texto_pdf:
                    docs["comprovante"] = arquivo
                    st.write(f"🔗 {nome} associado a {docs['nf'].name}")
                    break
    
    pdf_resultados = {}
    
    # Criamos os PDFs finais
    for fornecedor, docs in agrupados.items():
        if docs["comprovante"]:
            merger = PdfMerger()
            temp_files = []
            
            for pdf in [docs["comprovante"], docs["nf"]]:
                temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(pdf.getbuffer())  
                temp_files.append(temp_path)
                merger.append(temp_path)
            
            nome_arquivo_final = docs["nf"].name  # Usa o nome da NF/boletos/invoice
            caminho_saida = os.path.join(tempfile.gettempdir(), nome_arquivo_final)
            merger.write(caminho_saida)
            merger.close()
            pdf_resultados[fornecedor] = caminho_saida
            st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
        else:
            st.warning(f"⚠️ Nenhum comprovante encontrado para {docs['nf'].name}")
    
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

        for fornecedor, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {fornecedor}",
                    data=file,
                    file_name=fornecedor,
                    mime="application/pdf"
                )
