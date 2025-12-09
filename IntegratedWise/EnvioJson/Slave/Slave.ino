// slave_modificado.ino
// Descrição: Código para o ESP32 (Slave/EndPoint).
// Ele lê 5 sensores analógicos, salva os dados em um log JSON local,
// e periodicamente tenta enviar os dados não enviados para o Gateway.
// **Versão atualizada com nova estrutura de dados do log.**

#include <Arduino.h>
#include "LoRaMESH.h"      // Biblioteca de comunicação LoRa
#include <SPIFFS.h>        // Para o sistema de arquivos do ESP32
#include <ArduinoJson.h>   // Para manipulação de JSON
#include <vector>          // Para gerenciar o log em memória

// --- Configuração dos Pinos ---
#define LORA_TX_PIN 17          // Pino Tx
#define LORA_RX_PIN 16          // Pino Rx

// --- Pinos dos Sensores (Todos devem ser pinos com capacidade de ADC) ---
#define SENSOR_PIN         34   // Pino para "Sensor"
#define TEMP_MANCAL1_PIN   35   // Pino para "TempMancal1"
#define TEMP_MANCAL2_PIN   32   // Pino para "TempMancal2"
#define TEMP_MANCAL3_PIN   33   // Pino para "TempMancal3"
#define TEMP_MANCAL4_PIN   25   // Pino para "TempMancal4"

// --- Configurações da Rede LoRa ---
#define GATEWAY_ID 0

// --- Definições dos Comandos LoRa (devem ser os mesmos do Master) ---
#define CMD_FROM_MASTER_CONFIG 0x10
#define CMD_FROM_MASTER_ACK    0x11
#define CMD_TO_GATEWAY_EVENT   0x20

// --- Configuração dos Arquivos e Constantes ---
#define CONFIG_FILE "/config.json"
#define LOG_FILE    "/log.jsonl"
const unsigned long INTERVALO_LEITURA = 30000; 
const unsigned long INTERVALO_REENVIO = 10000; 
const unsigned long TIMEOUT_ACK = 10000;       
const size_t LIMITE_LINHAS_LOG = 10; // Limite de linhas para o arquivo de log

// --- Variáveis Globais de Controle ---
unsigned long ultimaLeitura = 0;
unsigned long ultimoReenvio = 0;
bool aguardandoAck = false;
unsigned long aguardandoAckDesde = 0;

// --- Objetos e Instâncias ---
HardwareSerial LoRaSerial(2);
LoRaMESH lora(&LoRaSerial);

// --- Protótipos de Funções ---
void salvarConfig(const String& jsonConfig);
void carregarConfig();
void registrarEvento();
void tentarReenvio();
void marcarEventoComoEnviado();
void displayFileContent(const char* filename);

void setup() {
  Serial.begin(115200);
  
  // Configura todos os pinos de sensor como entrada
  pinMode(SENSOR_PIN, INPUT);
  pinMode(TEMP_MANCAL1_PIN, INPUT);
  pinMode(TEMP_MANCAL2_PIN, INPUT);
  pinMode(TEMP_MANCAL3_PIN, INPUT);
  pinMode(TEMP_MANCAL4_PIN, INPUT);

  Serial.println("\n--- [SLAVE] Inicializando EndPoint ---");
  Serial.println("--- Envie 'L' para ver o log.jsonl ---");

  if (!SPIFFS.begin(true)) {
    Serial.println("[ERRO] Falha ao montar o SPIFFS.");
    while (true) delay(1000);
  }
  Serial.println("[OK] Sistema de arquivos montado.");
  carregarConfig();

  LoRaSerial.begin(9600, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  lora.begin();
  lora.deviceId = lora.localId;
  lora.debug_serial = false; 
  Serial.print("[OK] Módulo LoRa iniciado. ID Local: ");
  Serial.println(lora.localId);
}

void loop() {
  // 1. Lógica de Recepção de Comandos LoRa
  uint16_t senderId;
  uint8_t receivedCommand;
  uint8_t payload[MAX_PAYLOAD_SIZE];
  uint8_t payloadSize;

  if (lora.ReceivePacketCommand(&senderId, &receivedCommand, payload, &payloadSize, 50)) {
    payload[payloadSize] = '\0';
    String msg = (char*)payload;
    Serial.print("[LORA] Comando recebido do ID ");
    Serial.print(senderId);
    Serial.print(" - CMD: 0x");
    Serial.println(receivedCommand, HEX);

    switch (receivedCommand) {
      case CMD_FROM_MASTER_ACK:
        marcarEventoComoEnviado();
        break;
      case CMD_FROM_MASTER_CONFIG:
        salvarConfig(msg);
        break;
      default:
        Serial.println("[AVISO] Comando LoRa desconhecido.");
        break;
    }
  }

  // 2. Lógica de Registro de Evento por tempo
  if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
    registrarEvento();
    ultimaLeitura = millis();
  }

  // 3. Lógica de Reenvio de Eventos para o Gateway
  if (millis() - ultimoReenvio >= INTERVALO_REENVIO) {
    tentarReenvio();
    ultimoReenvio = millis();
  }

  // 4. Lógica de Timeout do ACK
  if (aguardandoAck && (millis() - aguardandoAckDesde > TIMEOUT_ACK)) {
      Serial.println("[TIMEOUT] Nenhum ACK recebido. Tentando reenviar na próxima vez.");
      aguardandoAck = false; 
  }

  // 5. Lógica para exibir arquivos via Monitor Serial
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == 'l' || command == 'L') {
      displayFileContent(LOG_FILE);
    }
  }
}

void carregarConfig() {
  if (SPIFFS.exists(CONFIG_FILE)) {
    File file = SPIFFS.open(CONFIG_FILE, "r");
    if (file) {
      Serial.println("[INIT] Arquivo de configuração encontrado. Carregando.");
      String configContent = file.readString();
      file.close();
      salvarConfig(configContent);
    }
  } else {
    Serial.println("[INIT] Nenhum config encontrado. Usando valores padrão.");
  }
}

void salvarConfig(const String& jsonConfig) {
  Serial.println("[CONFIG] Aplicando e salvando nova configuração...");
  File f = SPIFFS.open(CONFIG_FILE, "w");
  if (!f) {
    Serial.println("[ERRO] Falha ao abrir config para escrita.");
    return;
  }
  f.print(jsonConfig);
  f.close();
  Serial.println("[CONFIG] Arquivo salvo. As novas configurações serão aplicadas.");
}

void registrarEvento() {
  Serial.println("\n[EVENTO] Lendo sensores e registrando localmente...");
  
  std::vector<String> lines;
  File readFile = SPIFFS.open(LOG_FILE, "r");
  if (readFile) {
    while (readFile.available()) {
      String line = readFile.readStringUntil('\n');
      if (line.length() > 0) {
        lines.push_back(line);
      }
    }
    readFile.close();
  }

  while (lines.size() >= LIMITE_LINHAS_LOG) {
    lines.erase(lines.begin());
  }

  // Cria o novo evento com a nova estrutura de dados
  StaticJsonDocument<256> doc;
  doc["Sensor"] = analogRead(SENSOR_PIN);
  doc["TempMancal1"] = analogRead(TEMP_MANCAL1_PIN);
  doc["TempMancal2"] = analogRead(TEMP_MANCAL2_PIN);
  doc["TempMancal3"] = analogRead(TEMP_MANCAL3_PIN);
  doc["TempMancal4"] = analogRead(TEMP_MANCAL4_PIN);
  doc["enviado"] = false;

  String novoLog;
  serializeJson(doc, novoLog);
  lines.push_back(novoLog);

  File writeFile = SPIFFS.open(LOG_FILE, "w");
  if (!writeFile) {
    Serial.println("[ERRO] Falha ao abrir log para escrita.");
    return;
  }
  for (const auto& line : lines) {
    writeFile.println(line);
  }
  writeFile.close();

  Serial.print("[LOG] Novo evento registrado: ");
  Serial.println(novoLog);
}

void tentarReenvio() {
  if (aguardandoAck) {
    Serial.println("[REENVIO] Aguardando ACK, pulando tentativa de envio.");
    return;
  }

  Serial.println("[REENVIO] Procurando por evento não enviado...");

  File logFile = SPIFFS.open(LOG_FILE, "r");
  if (!logFile || logFile.size() == 0) {
    if(logFile) logFile.close();
    Serial.println("[REENVIO] Log vazio ou inexistente. Nada a fazer.");
    return;
  }
  
  String linhaParaEnviar;
  bool eventoEncontrado = false;

  while (logFile.available()) {
    String line = logFile.readStringUntil('\n');
    if (line.length() == 0) continue;

    StaticJsonDocument<256> doc;
    deserializeJson(doc, line);

    if (doc["enviado"] == false) {
        linhaParaEnviar = line;
        eventoEncontrado = true;
        break;
    }
  }
  logFile.close();

  if (eventoEncontrado) {
      Serial.print("[LORA] Tentando enviar para Gateway: ");
      Serial.println(linhaParaEnviar);

      if (lora.PrepareFrameCommand(GATEWAY_ID, CMD_TO_GATEWAY_EVENT, (uint8_t*)linhaParaEnviar.c_str(), linhaParaEnviar.length())) {
          lora.SendPacket();
          aguardandoAck = true;
          aguardandoAckDesde = millis();
      } else {
          Serial.println("[ERRO] Falha ao preparar frame LoRa. Tentará novamente mais tarde.");
      }
  } else {
      Serial.println("[REENVIO] Nenhum evento pendente encontrado.");
  }
}

void marcarEventoComoEnviado() {
    if (!aguardandoAck) return;
    
    Serial.println("[ACK] ACK recebido! Marcando evento como enviado.");
    aguardandoAck = false;

    File logFile = SPIFFS.open(LOG_FILE, "r");
    File tempFile = SPIFFS.open("/temp_log.jsonl", "w");
    if (!logFile || !tempFile) {
        Serial.println("[ERRO] Falha ao abrir arquivos para atualização do log.");
        if(logFile) logFile.close();
        if(tempFile) tempFile.close();
        return;
    }

    bool ackAplicado = false;
    while (logFile.available()) {
        String line = logFile.readStringUntil('\n');
        if (line.length() == 0) continue;
        
        StaticJsonDocument<256> doc;
        deserializeJson(doc, line);
        
        if (!ackAplicado && doc["enviado"] == false) {
            doc["enviado"] = true;
            ackAplicado = true;
            String linhaModificada;
            serializeJson(doc, linhaModificada);
            tempFile.println(linhaModificada);
        } else {
            tempFile.println(line);
        }
    }
    logFile.close();
    tempFile.close();

    SPIFFS.remove(LOG_FILE);
    SPIFFS.rename("/temp_log.jsonl", LOG_FILE);
    Serial.println("[LOG] Arquivo de log atualizado com sucesso.");
}

void displayFileContent(const char* filename) {
  Serial.println();
  Serial.print("--- Conteudo do arquivo: ");
  Serial.println(filename);
  Serial.println("---");
  File file = SPIFFS.open(filename, "r");
  if (!file) {
    Serial.print("[ERRO] Falha ao abrir o arquivo '");
    Serial.print(filename);
    Serial.println("' para leitura.");
    return;
  }
  if (file.size() == 0) {
      Serial.println("(Arquivo vazio)");
  } else {
      while (file.available()) {
        Serial.write(file.read());
      }
  }
  file.close();
  Serial.println("\n--- Fim do arquivo ---");
}
