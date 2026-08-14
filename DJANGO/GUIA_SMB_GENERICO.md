# Guia SMB Genérico - Mapeamento de Unidades de Rede

## Visão Geral

O sistema agora suporta **qualquer servidor SMB**, não apenas Azure Storage. Você pode mapear:
- NAS (Network Attached Storage)
- Windows Server
- Compartilhamentos locais
- Servidores Linux com Samba
- Qualquer outro servidor SMB 3.0

**Não é necessário Azure Storage!**

---

## Teste Básico (Sem Configuração)

Execute o teste para verificar se o módulo está funcionando:

```bash
cd DJANGO
python test_smb_generic.py
```

**Resultado esperado:**
```
✅ GENERIC SMB MODULE TESTS COMPLETED
📋 Summary:
- Drive listing: ✅ Working
- Available drive detection: ✅ Working
- Drive info retrieval: ✅ Working
- Generic SMB mapping: ✅ Ready
```

---

## Como Usar

### Opção 1: Via Python

```python
from core.network_drive import drive_manager

# Mapear um compartilhamento NAS
result = drive_manager.map_any_smb(
    share_path=r'\\192.168.1.100\public',
    drive_letter='Z',
    persistent=True,
    username='admin',
    password='sua_senha'
)

# Mapear compartilhamento Windows Server
result = drive_manager.map_any_smb(
    share_path=r'\\server-name\shared-folder',
    drive_letter='X',
    persistent=True,
    username='domain\\user',
    password='sua_senha'
)

# Mapear compartilhamento público (sem senha)
result = drive_manager.map_any_smb(
    share_path=r'\\192.168.1.100\public',
    drive_letter='Y',
    persistent=True
)
```

### Opção 2: Via Comando Windows

```cmd
# NAS
net use Z: \\192.168.1.100\public /user:admin senha /persistent:yes

# Windows Server
net use X: \\server-name\shared-folder /user:domain\user senha /persistent:yes

# Compartilhamento público
net use Y: \\192.168.1.100\public /persistent:yes
```

### Opção 3: Via API REST

```bash
# Iniciar servidor
cd DJANGO
python manage.py runserver

# Mapear compartilhamento SMB
curl -X POST http://localhost:8000/api/files/network-drives/map_smb_share/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "share_path": "\\\\192.168.1.100\\public",
    "drive_letter": "Z",
    "persistent": true,
    "username": "admin",
    "password": "senha"
  }'
```

---

## Exemplos Práticos

### Exemplo 1: NAS Synology

```python
result = drive_manager.map_any_smb(
    share_path=r'\\synology-nas\engineering',
    drive_letter='Z',
    persistent=True,
    username='eng_user',
    password='synology_password'
)
```

### Exemplo 2: Windows Server 2019

```python
result = drive_manager.map_any_smb(
    share_path=r'\\fileserver.company.local\cad-files',
    drive_letter='X',
    persistent=True,
    username='COMPANY\\cad_user',
    password='windows_password'
)
```

### Exemplo 3: Linux Samba Server

```python
result = drive_manager.map_any_smb(
    share_path=r'\\192.168.1.50\projects',
    drive_letter='Y',
    persistent=True,
    username='samba_user',
    password='linux_password'
)
```

### Exemplo 4: Compartilhamento Local

```python
result = drive_manager.map_any_smb(
    share_path=r'\\localhost\c$\Users\Public',
    drive_letter='W',
    persistent=False
)
```

---

## API Endpoints

### Novo Endpoint: map_smb_share

```http
POST /api/files/network-drives/map_smb_share/
Content-Type: application/json

{
  "share_path": "\\\\192.168.1.100\\share",
  "drive_letter": "Z",
  "persistent": true,
  "username": "user",
  "password": "pass"
}
```

**Parâmetros:**
- `share_path` (obrigatório): Caminho SMB do compartilhamento
- `drive_letter` (opcional): Letra do drive (auto-seleciona se não informado)
- `persistent` (opcional): Manter após reboot (default: true)
- `username` (opcional): Usuário SMB (se necessário)
- `password` (opcional): Senha SMB (se necessário)

---

## Integração com AutoCAD

### Passo 1: Mapear o Drive

```python
from core.network_drive import drive_manager

# Mapear NAS com arquivos CAD
result = drive_manager.map_any_smb(
    share_path=r'\\nas-server\cad-projects',
    drive_letter='Z',
    persistent=True,
    username='cad_user',
    password='cad_password'
)
```

### Passo 2: Usar no AutoCAD

1. Abra o AutoCAD
2. File → Open
3. Navegue para Z:\
4. Abra o arquivo DWG

**Performance:** O AutoCAD trata Z: como disco local, performance nativa SMB 3.0.

---

## Comparação: Azure vs Genérico

| Recurso | Azure Files | SMB Genérico |
|---------|-------------|--------------|
| Azure Storage | ✅ Obrigatório | ❌ Não necessário |
| NAS | ❌ Não suporta | ✅ Suporta |
| Windows Server | ❌ Não suporta | ✅ Suporta |
| Linux Samba | ❌ Não suporta | ✅ Suporta |
| Compartilhamento Local | ❌ Não suporta | ✅ Suporta |
| AutoCAD | ✅ Sim | ✅ Sim |
| Performance | ✅ Alta | ✅ Alta |

---

## Troubleshooting

### Problema: "Access Denied"

**Causa:** Credenciais incorretas ou permissões insuficientes

**Solução:**
1. Verifique usuário e senha
2. Verifique permissões no servidor SMB
3. Tente sem senha se for compartilhamento público

### Problema: "Network Path Not Found"

**Causa:** Caminho SMB incorreto ou servidor offline

**Solução:**
1. Verifique se o servidor está acessível
2. Teste com `ping 192.168.1.100`
3. Verifique o nome do compartilhamento

### Problema: "Drive Already in Use"

**Causa:** A letra de drive já está mapeada

**Solução:**
```python
# Desmapear primeiro
drive_manager.unmap_drive('Z', force=True)
# Ou usar outra letra
drive_manager.map_any_smb(share_path='\\...', drive_letter='Y')
```

### Problema: "No Available Drive Letters"

**Causa:** Todas as letras de Z a D estão em uso

**Solução:**
```python
# Desmapear drives não usados
# Ou usar range diferente
available = drive_manager.get_available_drive_letter(start='Y', end='E')
```

---

## Teste com Seu Servidor SMB

### Script de Teste Interativo

```python
from core.network_drive import drive_manager

# Solicitar informações do usuário
share_path = input("Caminho SMB (ex: \\\\192.168.1.100\\share): ")
drive_letter = input("Letra do drive (deixe vazio para auto): ") or None
username = input("Usuário (deixe vazio se público): ") or None
password = input("Senha (deixe vazio se pública): ") or None

# Mapear
result = drive_manager.map_any_smb(
    share_path=share_path,
    drive_letter=drive_letter,
    persistent=False,  # Não persistir para teste
    username=username,
    password=password
)

if result['success']:
    print(f"✅ {result['message']}")
    
    # Testar acesso
    access = drive_manager.test_drive_access(result['drive_letter'])
    print(f"   Acesso: {access['message']}")
    
    # Desmapear
    drive_manager.unmap_drive(result['drive_letter'], force=True)
    print(f"   Desmapeado para teste")
else:
    print(f"❌ {result['message']}")
```

---

## Vantagens do SMB Genérico

1. **Flexibilidade:** Funciona com qualquer servidor SMB
2. **Custo:** Sem custo de Azure Storage
3. **Privacidade:** Dados no seu próprio servidor
4. **Performance:** Rede local mais rápida que nuvem
5. **Controle:** Controle total sobre o servidor

---

## Quando Usar Azure vs Genérico

### Use Azure Files Quando:
- Precisa de escalabilidade infinita
- Quer backup automático na nuvem
- Equipes distribuídas globalmente
- Não quer manter servidores

### Use SMB Genérico Quando:
- Já tem NAS ou servidor Windows
- Prefere controle local
- Quer reduzir custos
- Equipe em um único local
- Requisitos de compliance local

---

## Próximos Passos

1. **Teste com seu servidor SMB atual**
2. **Migre arquivos CAD para o compartilhamento**
3. **Configure mapeamento automático para usuários**
4. **Treine equipe no novo fluxo de trabalho**

---

## Suporte

Para problemas:
1. Execute `python test_smb_generic.py` para diagnóstico
2. Verifique logs do servidor SMB
3. Teste com `net use` no Windows para isolamento
4. Consulte documentação do seu servidor SMB

---

*Guia atualizado em 23 de Julho de 2026*
