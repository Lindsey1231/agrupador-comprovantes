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
    
    # Agrupa documentos e comprovantes por CNPJ
    grupos_cnpj = {}
    for arquivo, nome, valores, cnpjs, tipo_arquivo in info_arquivos:
        for cnpj in cnpjs:
            if cnpj not in grupos_cnpj:
                grupos_cnpj[cnpj] = {"documentos": [], "comprovantes": []}
            if tipo_arquivo == "documento":
                grupos_cnpj[cnpj]["documentos"].append((arquivo, nome, valores))
            elif tipo_arquivo == "comprovante":
                grupos_cnpj[cnpj]["comprovantes"].append((arquivo, nome, valores))
    
    # Etapa 1: Junta os que possuem múltiplos pagamentos de um mesmo fornecedor (CNPJ + VALOR)
    for cnpj, grupo in grupos_cnpj.items():
        documentos = grupo["documentos"]
        comprovantes = grupo["comprovantes"]
        
        # Se houver mais de um documento ou comprovante para o mesmo CNPJ, avalia CNPJ + VALOR
        if len(documentos) > 1 or len(comprovantes) > 1:
            for doc, nome_doc, valores_doc in documentos:
                melhor_correspondencia = None
                
                # Tenta correspondência por valor dentro do mesmo CNPJ
                for comprovante, nome_comp, valores_comp in comprovantes:
                    if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                        melhor_correspondencia = comprovante
                        break
                
                # Se encontrou correspondência, adiciona ao grupo
                if melhor_correspondencia:
                    agrupados[nome_doc] = [melhor_correspondencia, doc]
                    # Remove o comprovante da lista para evitar duplicação
                    comprovantes.remove((melhor_correspondencia, nome_comp, valores_comp))
    
    # Etapa 2: Junta os que possuem apenas 1 pagamento de um fornecedor (apenas CNPJ)
    for cnpj, grupo in grupos_cnpj.items():
        documentos = grupo["documentos"]
        comprovantes = grupo["comprovantes"]
        
        # Se houver apenas um documento e um comprovante para o mesmo CNPJ, associa por CNPJ
        if len(documentos) == 1 and len(comprovantes) == 1:
            doc, nome_doc, valores_doc = documentos[0]
            comprovante, nome_comp, valores_comp = comprovantes[0]
            
            # Adiciona ao grupo
            agrupados[nome_doc] = [comprovante, doc]
    
    # Etapa 3: Junta os que sobraram, considerando apenas o VALOR
    documentos_restantes = []
    comprovantes_restantes = []
    
    # Coleta documentos e comprovantes que ainda não foram agrupados
    for cnpj, grupo in grupos_cnpj.items():
        documentos_restantes.extend(grupo["documentos"])
        comprovantes_restantes.extend(grupo["comprovantes"])
    
    # Remove documentos e comprovantes que já foram agrupados
    documentos_restantes = [doc for doc in documentos_restantes if doc[1] not in agrupados]
    comprovantes_restantes = [comp for comp in comprovantes_restantes if not any(comp[0] in lista for lista in agrupados.values())]
    
    # Tenta correspondência por valor
    for doc, nome_doc, valores_doc in documentos_restantes:
        melhor_correspondencia = None
        
        for comprovante, nome_comp, valores_comp in comprovantes_restantes:
            if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                melhor_correspondencia = comprovante
                break
        
        # Se encontrou correspondência, adiciona ao grupo
        if melhor_correspondencia:
            agrupados[nome_doc] = [melhor_correspondencia, doc]
            # Remove o comprovante da lista para evitar duplicação
            comprovantes_restantes.remove((melhor_correspondencia, nome_comp, valores_comp))
    
    # Adiciona comprovantes sem correspondência
    for comprovante, nome_comp, valores_comp in comprovantes_restantes:
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
    
    # Adicionando um key único ao file_uploader
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True, key="file_uploader")
    
    if arquivos and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs", key="process_button"):
            pdf_resultados, zip_path = organizar_por_cnpj_e_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(
                        label=f"📄 Baixar {nome}",
                        data=f,
                        file_name=nome,
                        mime="application/pdf",
                        key=f"download_{nome}"  # Adicionando um key único para cada botão de download
                    )
            
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="📥 Baixar todos como ZIP",
                    data=f,
                    file_name="comprovantes_agrupados.zip",
                    mime="application/zip",
                    key="download_zip"  # Adicionando um key único para o botão de download do ZIP
                )

if __name__ == "__main__":
    main()
