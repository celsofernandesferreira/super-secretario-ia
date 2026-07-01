# 📖 Base de Conhecimento: Casos Reais de Suporte e Infraestrutura IT

Esta base de dados serve como guia operacional e filosofia técnica para a resolução de incidentes de Helpdesk, Administração de Sistemas e Infraestrutura de Rede.

---

## 🛠️ Domínio 1: Administração de Sistemas & Active Directory (AD)

### Caso 1.1: Utilizador Bloqueado e Falhas Sucessivas de Autenticação
* **Cenário:** Um utilizador da contabilidade liga a informar que a sua conta de domínio é bloqueada de 15 em 15 minutos, mesmo após o Helpdesk efetuar o *unlock* na consola `Active Directory Users and Computers (ADUC)`.
* **Resolução Operacional (Filosofia Celso):**
  1. **Auditoria de Eventos:** Aceder ao Domain Controller (DC) e analisar o `Event Viewer`. Filtrar os Logs de Segurança pelo **Event ID 4740** (A conta de utilizador foi bloqueada).
  2. **Identificação da Origem:** Verificar o campo "Caller Computer Name" no log para rastrear a máquina exata que está a enviar as credenciais incorretas.
  3. **Diagnóstico no Cliente:** Deslocar ou aceder remotamente à máquina de origem. Causas comuns: credenciais antigas em cache no `Credential Manager` do Windows, drives de rede mapeadas com password antiga, ou serviços de segundo plano/scripts com credenciais desatualizadas.
  4. **Correção:** Limpar o Gestor de Credenciais, reiniciar a máquina e testar nova autenticação.

### Caso 1.2: Replicação de DNS e Falhas de Acesso a Partilhas (SysVol)
* **Cenário:** Após a quebra de energia num dos escritórios, os computadores clientes não conseguem aplicar as `Group Policy Objects (GPOs)` e perdem o acesso à pasta `\\dominio.local\sysvol`.
* **Resolução Operacional (Filosofia Celso):**
  1. **Validação de DNS:** Executar `nslookup` a partir do cliente para garantir que os registos `SRV` do AD estão a apontar para os Domain Controllers ativos.
  2. **Análise de Replicação:** No DC, abrir a Linha de Comandos (CMD) como Administrador e executar `repadmin /replsummary` e `repadmin /showrepl` para verificar se a replicação entre Domain Controllers está em falha.
  3. **Correção do Serviço DFS-R:** Se houver erros de replicação na pasta SYSVOL, reiniciar o serviço `Distributed File System Replication` via PowerShell:
     ```powershell
     Restart-Service DFSR
     ```
  4. Caso o estado seja de *Journal Wrap* ou *Inbound replication blocked*, forçar uma replicação não-autoritativa alterando o registo `msDFSR-Enabled` para `FALSE` e depois `TRUE` via `ADSI Edit`.

---

## 🌐 Domínio 2: Redes de Computadores & Conectividade

### Caso 2.1: Conflito de IP Estático vs Dinâmico (DHCP Rogue/Exhaustion)
* **Cenário:** Múltiplos utilizadores numa VLAN de produção começam a perder conectividade intermitente e o Windows apresenta o alerta "Existe um conflito de endereços IP".
* **Resolução Operacional (Filosofia Celso):**
  1. **Isolamento de Erro:** Executar `arp -a` na máquina afetada para capturar o endereço MAC do dispositivo que está a responder pelo mesmo IP.
  2. **Análise do Servidor DHCP:** Aceder ao servidor DHCP (Windows Server ou Router), verificar a consola de `Leases` e conferir se o IP em conflito faz parte de um *Scope* dinâmico mas foi configurado estaticamente num dispositivo sem exclusão.
  3. **Remediação Imediata:** Libertar e renovar o IP na máquina do utilizador afetado:
     ```cmd
     ipconfig /release
     ipconfig /renew
     ```
  4. **Medida Preventiva (Security):** Criar uma exclusão no scope do DHCP para o IP estático em questão ou configurar uma reserva pelo MAC Address. Para evitar servidores DHCP falsos na rede, garantir que o *DHCP Snooping* está ativo nos switches geríveis da infraestrutura.

### Caso 2.2: Isolamento de Falhas em VLANs e Trunks
* **Cenário:** Um novo PC de engenharia foi ligado a uma tomada de rede mas não recebe IP por DHCP e fica com o endereço `169.254.X.X` (APIPA).
* **Resolução Operacional (Filosofia Celso):**
  1. **Análise de Camada Física:** Verificar se o LED de link da placa de rede e da porta do switch está verde/ativo.
  2. **Configuração da Porta do Switch:** Aceder à consola de gestão do switch. Verificar se a porta está associada à VLAN correta (ex: VLAN 10 - Dados) em modo `Access`.
  3. **Verificação de Trunk:** Se o servidor DHCP estiver numa VLAN diferente, verificar se as portas de interligação (Trunks) entre switches e o router estão a permitir a passagem de tags da VLAN 10 (Protocolo `802.1Q`).
  4. **IP Helper Address:** Garantir que a interface de gateway da VLAN no router tem o comando `ip helper-address [IP_do_Servidor_DHCP]` configurado para reencaminhar os pacotes de broadcast do DHCP.

---

## ☁️ Domínio 3: Cloud, Automação & Scripts de Manutenção

### Caso 3.1: Automatização de Auditoria de Backups Desatualizados
* **Cenário:** O SysAdmin precisa de garantir que nenhum servidor de ficheiros fica mais do que 24 horas sem gerar logs de integridade de backup.
* **Resolução Operacional (Filosofia Celso):**
  1. **Construção de Script PowerShell:** Criar uma tarefa agendada que corra um script de verificação diária:
     ```powershell
     $Path = "C:\Backups\Logs\"
     $Limit = (Get-Date).AddDays(-1)
     $Files = Get-ChildItem -Path $Path -Filter "*.log" | Where-Object { $_.LastWriteTime -lt $Limit }
     if ($Files) {
         Send-MailMessage -From "alerta@dominio.com" -To "celso.ferreira@it.com" -Subject "ALERTA: Falha de Backup" -Body "Logs desatualizados!" -SmtpServer "smtp.dominio.com"
     }
     ```
  2. **Monitorização:** Associar o output e os erros do script ao ficheiro centralizado de telemetria para auditorias de conformidade (*Compliance*).
