# Guia Passo a Passo - Teste Azure Files 2

## Pré-requisitos

- Windows 7 ou superior
- Python 3.8+ instalado
- Conta Azure Storage criada
- File Share criado no Azure Storage

---

## Passo 1: Configurar Credenciais Azure

### 1.1 Obter Credenciais do Azure

1. Acesse [Azure Portal](https://portal.azure.com)
2. Vá para seu Storage Account
3. Clique em "Access keys"
4. Copie:
   - **Storage account name** (ex: `mukandafilevault`)
   - **Key** (chave de acesso)
5. Vá para "File shares"
6. Anote o **nome do share** (ex: `filevault`)

### 1.2 Configurar Variáveis de Ambiente (Windows PowerShell)

```powershell
# Abra o PowerShell como Administrador
$env:AZURE_STORAGE_ACCOUNT_NAME = "seu_account_name"
$env:AZURE_STORAGE_ACCOUNT_KEY = "sua_chave_aqui"
$env:AZURE_STORAGE_SHARE_NAME = "filevault"

# Verificar se foram configuradas
echo $env:AZURE_STORAGE_ACCOUNT_NAME
echo $env:AZURE_STORAGE_SHARE_NAME
```

### 1.3 Configurar Variáveis de Ambiente (Permanente)

```powershell
# Para persistir após reiniciar
setx AZURE_STORAGE_ACCOUNT_NAME "seu_account_name"
setx AZURE_STORAGE_ACCOUNT_KEY "sua_chave_aqui"
setx AZURE_STORAGE_SHARE_NAME "filevault"
```

---

## Passo 2: Teste Básico (Sem Credenciais Azure)

Este teste verifica se o módulo está funcionando sem precisar de credenciais.

### 2.1 Executar Teste Básico

```bash
cd c:\Users\HOSSIDEV\Documents\PROGRAMACAO PROJECTOS\mukanda-cloud\DJANGO
python test_network_drive_basic.py
```

### 2.2 Resultado Esperado

```
=============================================
NETWORK DRIVE MAPPING BASIC TEST
=============================================

1. Testing List Mapped Drives:
---------------------------------------------
✅ Successfully listed 0 mapped drive(s)

2. Testing Drive Status Check:
---------------------------------------------
✅ Drive Z: mapped status: False

3. Testing Available Drive Letter Detection:
---------------------------------------------
✅ Available drive letter: Z:

4. Testing Drive Info Retrieval:
---------------------------------------------
✅ Drive Z: not mapped (correct behavior)

5. Testing SMB Path Generation:
---------------------------------------------
⚠️  Expected error (no Azure config): AZURE_STORAGE_ACCOUNT_NAME not configured

=============================================
✅ BASIC NETWORK DRIVE MODULE TESTS PASSED
=============================================
```

**Se passou**: O módulo está funcionando corretamente.
**Se falhou**: Verifique se o Python e Django estão instalados corretamente.

---

## Passo 3: Teste Completo (Com Credenciais Azure)

### 3.1 Verificar Configuração

```bash
cd c:\Users\HOSSIDEV\Documents\PROGRAMACAO PROJECTOS\mukanda-cloud\DJANGO
python test_network_drive.py
```

### 3.2 Resultado Esperado (Com Credenciais)

```
=============================================
NETWORK DRIVE MAPPING TEST - AZURE FILES 2
=============================================

1. Checking Azure Configuration:
---------------------------------------------
✅ SMB Path: \\mukandafilevault.file.core.windows.net\filevault
   Account: mukandafilevault
   Share: filevault

2. Listing Current Mapped Drives:
---------------------------------------------
Found 0 mapped drive(s)

3. Finding Available Drive Letter:
---------------------------------------------
✅ Available drive letter: Z:

4. Mapping Azure Files to Network Drive:
---------------------------------------------
Attempting to map Z: to Azure Files...
✅ Drive Z: successfully mapped to \\mukandafilevault.file.core.windows.net\filevault

5. Verifying Drive Mapping:
---------------------------------------------
✅ Drive Z: is mapped
   Path: \\mukandafilevault.file.core.windows.net\filevault
   Status: Microsoft Windows Network

6. Testing Drive Access:
---------------------------------------------
✅ Drive Z: is accessible
   Items in root: 0

7. Listing Mapped Drives After Mapping:
---------------------------------------------
Found 1 mapped drive(s):
  📁 Z: -> \\mukandafilevault.file.core.windows.net\filevault

8. Unmapping Test Drive:
---------------------------------------------
✅ Drive Z: successfully unmapped

9. Verifying Drive Unmapping:
---------------------------------------------
✅ Drive Z: is successfully unmapped

=============================================
✅ NETWORK DRIVE MAPPING TESTS COMPLETED
=============================================
```

### 3.3 Se Der Erro

**Erro: "AZURE_STORAGE_ACCOUNT_NAME not configured"**
- Verifique se as variáveis de ambiente foram configuradas
- Feche e abra o PowerShell novamente

**Erro: "Share does not exist"**
- Verifique se o File Share existe no Azure Portal
- Confirme o nome do share está correto

**Erro: "Network connectivity issues"**
- Verifique sua conexão com a internet
- Confirme que o firewall não bloqueia Azure Storage

---

## Passo 4: Teste Manual via Windows

### 4.1 Mapear Manualmente

Abra o **Prompt de Comando** como Administrador:

```cmd
net use Z: \\seu_account.file.core.windows.net\filevault /user:seu_account sua_chave /persistent:yes
```

### 4.2 Verificar no Windows Explorer

1. Abra o Windows Explorer
2. Procure pela unidade Z:
3. Deve aparecer como "Network Drive"

### 4.3 Desmapear

```cmd
net use Z: /delete /yes
```

---

## Passo 5: Teste via API REST

### 5.1 Iniciar Servidor Django

```bash
cd c:\Users\HOSSIDEV\Documents\PROGRAMACAO PROJECTOS\mukanda-cloud\DJANGO
python manage.py runserver
```

### 5.2 Testar Endpoints (via curl ou Postman)

#### Listar Drives
```bash
curl -X GET http://localhost:8000/api/files/network-drives/list_drives/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Obter Caminho SMB
```bash
curl -X GET http://localhost:8000/api/files/network-drives/azure_smb_path/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Mapear Azure Files
```bash
curl -X POST http://localhost:8000/api/files/network-drives/map_azure_files/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"drive_letter\": \"Z\", \"persistent\": true}"
```

#### Desmapear Drive
```bash
curl -X POST http://localhost:8000/api/files/network-drives/unmap_drive/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"drive_letter\": \"Z\", \"force\": true}"
```

---

## Passo 6: Teste com AutoCAD (Opcional)

### 6.1 Mapear o Drive

```bash
python test_network_drive.py
# Ou use a API para mapear permanentemente
```

### 6.2 Criar Arquivo de Teste

1. Abra o Windows Explorer
2. Vá para Z: (ou a letra mapeada)
3. Crie um arquivo de teste
4. Copie um arquivo DWG pequeno para teste

### 6.3 Abrir no AutoCAD

1. Abra o AutoCAD
2. File → Open
3. Navegue para Z:\
4. Abra o arquivo DWG
5. Verifique a performance

### 6.4 Performance Esperada

- Arquivo 10MB: 1-2 segundos
- Arquivo 50MB: 3-5 segundos
- Arquivo 100MB: 5-8 segundos

---

## Passo 7: Limpeza

### 7.1 Desmapear Todos os Drives de Teste

```bash
# Via Python
python -c "from core.network_drive import drive_manager; drive_manager.unmap_drive('Z', force=True)"

# Via Windows
net use Z: /delete /yes
net use X: /delete /yes
# Repita para outras letras usadas
```

### 7.2 Limpar Variáveis de Ambiente (Opcional)

```powershell
# Remover variáveis temporárias
$env:AZURE_STORAGE_ACCOUNT_NAME = ""
$env:AZURE_STORAGE_ACCOUNT_KEY = ""
$env:AZURE_STORAGE_SHARE_NAME = ""

# Remover variáveis permanentes
setx AZURE_STORAGE_ACCOUNT_NAME ""
setx AZURE_STORAGE_ACCOUNT_KEY ""
setx AZURE_STORAGE_SHARE_NAME ""
```

---

## Checklist de Teste

- [ ] Variáveis de ambiente configuradas
- [ ] Teste básico passou
- [ ] Teste completo passou
- [ ] Mapeamento manual funcionou
- [ ] Drive aparece no Windows Explorer
- [ ] API REST responde corretamente
- [ ] AutoCAD abre arquivos da unidade mapeada
- [ ] Performance é aceitável
- [ ] Desmapeamento funciona
- [ ] Limpeza concluída

---

## Solução de Problemas

### Problema: "Access Denied"

**Causa**: Credenciais incorretas ou IP não autorizado

**Solução**:
1. Verifique a chave do Azure Storage
2. Configure IP whitelist no Azure Portal
3. Verifique se a conta está ativa

### Problema: "Drive Already in Use"

**Causa**: A letra de drive já está mapeada

**Solução**:
```bash
# Desmapear primeiro
net use Z: /delete /yes
# Ou usar outra letra
python -c "from core.network_drive import drive_manager; print(drive_manager.get_available_drive_letter())"
```

### Problema: "No Available Drive Letters"

**Causa**: Todas as letras de Z a D estão em uso

**Solução**:
1. Desmapear drives não usados
2. Usar range diferente: `get_available_drive_letter(start='Y', end='E')`

### Problema: "Slow Performance"

**Causa**: Conexão de internet lenta ou Azure Storage em região distante

**Solução**:
1. Use Azure Storage na mesma região dos usuários
2. Verifique velocidade da conexão
3. Considere upgrade do tier do Azure Files

---

## Suporte

Se encontrar problemas:
1. Verifique os logs em `DJANGO/logs/` (se existirem)
2. Execute `test_network_drive_basic.py` para diagnóstico
3. Consulte `AZURE_FILES_2_NETWORK_DRIVE.md` para documentação técnica
4. Verifique o Azure Portal para status do Storage Account

---

## Próximos Passos Após Teste

1. **Configurar para Produção**:
   - Usar Managed Identity em vez de account keys
   - Configurar Redis para IOPS tracking
   - Implementar backup automático

2. **Deploy para Usuários**:
   - Criar script de instalação automática
   - Configurar Group Policy para mapeamento
   - Treinar usuários

3. **Monitoramento**:
   - Configurar Azure Monitor
   - Configurar alertas de performance
   - Monitorar uso de IOPS

---

*Guia atualizado em 22 de Julho de 2026*
