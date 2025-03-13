import streamlit as st
import os
from PyPDF2 import PdfMerger
import tempfile

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    st.write("### Arquivos detectados:")
    
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        
        if any(kw in nome.upper() for kw in ["NF", "BOLETO", "INVOICE"]):
            chave = "-".join(nome.split("-")[:2]).strip()  # Usa Banco + Número para identificação
            fornecedor_nome = nome.split("-")[-1].strip().replace(".pdf", "")  # Obtém o nome do fornecedor completo
            if chave not in agrupados:
                agrupados[chave] = {"fornecedor": fornecedor_nome, "arquivos": []}
            agrupados[chave]["arquivos"].append(arquivo)
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL")
        elif any(kw in nome.upper() for kw in ["PIX", "COMPROVANTE", "PAGAMENTO", "TRANSFERENCIA"]):
            # Associar comprovante ao fornecedor correto
            fornecedor_nome = nome.split("-")[-1].strip().replace(".pdf", "")
            for chave, dados in agrupados.items():
                if dados["fornecedor"].lower() in fornecedor_nome.lower():
                    agrupados[chave]["arquivos"].insert(0, arquivo)  # Insere o comprovante primeiro
                    st.write(f"🔗 {nome} associado a {chave}")
                    break
    
    pdf_resultados = {}
    
    for chave, dados in agrupados.items():
        lista_arquivos = dados["arquivos"]
        if len(lista_arquivos) > 1:
            merger = PdfMerger()
            temp_files = []
            
            for pdf in lista_arquivos:
                temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(pdf.getbuffer())  
                temp_files.append(temp_path)
                merger.append(temp_path)
            
            nome_arquivo_final = lista_arquivos[1].name  # Usa o nome do documento principal como nome final
            caminho_saida = os.path.join(tempfile.gettempdir(), nome_arquivo_final)
            merger.write(caminho_saida)
            merger.close()
            pdf_resultados[chave] = caminho_saida
            st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
        else:
            st.warning(f"⚠️ Nenhum comprovante encontrado para {chave}")
    
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


