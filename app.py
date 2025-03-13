import streamlit as st
import os
import tempfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar o nome do fornecedor."""
    try:
        reader = PdfReader(arquivo)
        texto = " \n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return texto.lower()
    except:
        return ""

def encontrar_nome_fornecedor(texto):
    """Busca um nome de fornecedor mais preciso no conteúdo do PDF."""
    linhas = texto.split("\n")
    for linha in linhas:
        if any(kw in linha.lower() for kw in ["ltda", "s.a", "me", "eireli", "ss", "associação", "empresa"]):
            return linha.strip()
    return ""

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    fornecedores = {}
    st.write("### Arquivos detectados:")
    
    # Identifica os documentos principais (NF, boleto ou invoice)
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        
        if nome.startswith("(BTG)") or nome.startswith("(INTER)") or nome.startswith("(BV)"):
            fornecedor_nome = encontrar_nome_fornecedor(texto_pdf)
            if fornecedor_nome:
                agrupados[nome] = {"nf": arquivo, "comprovante": None, "fornecedor": fornecedor_nome}
                fornecedores[fornecedor_nome.lower()] = nome
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL para {fornecedor_nome}")
    
    # Associa os comprovantes de pagamento aos documentos principais
    for arquivo in arquivos:
        nome = arquivo.name
        if nome.lower().startswith("pix") or "pagamento" in nome.lower() or "comprovante" in nome.lower():
            texto_pdf = extrair_texto_pdf(arquivo)
            fornecedor_encontrado = encontrar_nome_fornecedor(texto_pdf)
            
            for fornecedor, chave in fornecedores.items():
                if fornecedor_encontrado and fornecedor_encontrado.lower() in fornecedor and chave != nome:
                    agrupados[chave]["comprovante"] = arquivo
                    st.write(f"🔗 {nome} associado a {chave}")
                    break
    
    pdf_resultados = {}
    
    # Criar PDFs finais para cada fornecedor
    for chave, docs in agrupados.items():
        if docs["comprovante"]:
            merger = PdfMerger()
            arquivos_adicionados = set()
            
            for pdf in [docs["comprovante"], docs["nf"]]:
                if pdf.name not in arquivos_adicionados:
                    temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                    with open(temp_path, "wb") as temp_file:
                        temp_file.write(pdf.getbuffer())  
                    merger.append(temp_path)
                    arquivos_adicionados.add(pdf.name)
            
            nome_arquivo_final = docs["nf"].name  # Mantém o nome original do documento principal
            caminho_saida = os.path.join(tempfile.gettempdir(), nome_arquivo_final)
            merger.write(caminho_saida)
            merger.close()
            pdf_resultados[chave] = caminho_saida
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

        for chave, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {chave}",
                    data=file,
                    file_name=chave,
                    mime="application/pdf"
                )
