import streamlit as st
import os
import tempfile
import re
import zipfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF garantindo melhor leitura."""
    try:
        reader = PdfReader(arquivo)
        texto = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texto.append(page_text)
        return " \n".join(texto)
    except Exception as e:
        st.error(f"Erro na extração do texto do arquivo {arquivo.name}: {str(e)}")
        return ""

def encontrar_valor(texto):
    """Busca valores monetários no conteúdo do PDF."""
    padrao_valor = re.findall(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})\b", texto)
    valores_processados = set()
    for valor in padrao_valor:
        try:
            valores_processados.add(float(valor.replace('.', '').replace(',', '.')))
        except ValueError:
            continue
    return valores_processados

def encontrar_cnpj(texto):
    """Busca CNPJs no conteúdo do PDF e padroniza a formatação."""
    padrao_cnpj = re.findall(r"\b\d{2}[.\/]?\d{3}[.\/]?\d{3}[\/\-]?\d{4}[\/\-]?\d{2}\b", texto)
    cnpjs = {re.sub(r'[^\d]', '', cnpj) for cnpj in padrao_cnpj} if padrao_cnpj else set()
    
    # Remove CNPJs que devem ser ignorados
    cnpjs_ignorados = {"19307785000178", "45121046000105", "28932155000185"}
    return cnpjs - cnpjs_ignorados

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo baseado no nome."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def organizar_por_cnpj_e_valor(arquivos):
    st.write("### Processando arquivos...")
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
    pdf_resultados = {}
    agrupados = {}
    info_arquivos = []
    
    # Extrai informações dos arquivos
    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        valores = encontrar_valor(texto_pdf)
        cnpjs = encontrar_cnpj(texto_pdf)
        tipo_arquivo = classificar_arquivo(nome)
        info_arquivos.append((arquivo, nome, valores, cnpjs, tipo_arquivo))
    
    # Associa documentos e comprovantes
    for doc, nome_doc, valores_doc, cnpjs_doc, tipo_doc in info_arquivos:
        if tipo_doc != "documento":
            continue
        
        melhor_correspondencia = None
        
        # 1. Tenta correspondência por CNPJ
        for comprovante, nome_comp, valores_comp, cnpjs_comp, tipo_comp in info_arquivos:
            if tipo_comp == "comprovante" and bool(cnpjs_comp & cnpjs_doc):
                melhor_correspondencia = comprovante
                break
        
        # 2. Se não encontrou por CNPJ, tenta por valor
        if not melhor_correspondencia:
            for comprovante, nome_comp, valores_comp, cnpjs_comp, tipo_comp in info_arquivos:
                if tipo_comp == "comprovante":
                    if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                        melhor_correspondencia = comprovante
                        break
        
        # Se encontrou correspondência, adiciona ao grupo
        if melhor_correspondencia:
            agrupados[nome_doc] = [melhor_correspondencia, doc]
    
    # Adiciona comprovantes sem correspondência
    for comprovante, nome_comp, valores_comp, cnpjs_comp, tipo_comp in info_arquivos:
        if tipo_comp == "comprovante" and not any(comprovante in lista for lista in agrupados.values()):
            nome_referencia = f"Sem Correspondência - {nome_comp}"
            agrupados[nome_referencia] = [comprovante]
    
    # Gera PDFs agrupados e arquivo ZIP
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for nome_final, arquivos in agrupados.items():
            merger = PdfMerger()
            for doc in arquivos:
                merger.append(doc)
            output_filename = nome_final
            output_path = os.path.join(temp_dir, output_filename)
            merger.write(output_path)
            merger.close()
            pdf_resultados[output_filename] = output_path
            zipf.write(output_path, arcname=output_filename)
            st.write(f"📂 Arquivo gerado: {output_filename}")
    
    return pdf_resultados, zip_path

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True)
    
    if arquivos and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs"):
            pdf_resultados, zip_path = organizar_por_cnpj_e_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(label=f"📄 Baixar {nome}", data=f, file_name=nome, mime="application/pdf")
            
            with open(zip_path, "rb") as f:
                st.download_button(label="📥 Baixar todos como ZIP", data=f, file_name="comprovantes_agrupados.zip", mime="application/zip")

if __name__ == "__main__":
    main()
