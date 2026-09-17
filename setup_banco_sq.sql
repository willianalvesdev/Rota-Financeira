-- MySQL 8.0.16+ (CHECK constraints). Execução repetida não apaga dados.
CREATE DATABASE IF NOT EXISTS `rota_financeira_db`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `rota_financeira_db`;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    senha VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_usuarios_email UNIQUE (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sessoes (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    usuario_id INT UNSIGNED NOT NULL,
    expira_em DATETIME NOT NULL,
    CONSTRAINT fk_sessoes_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_sessoes_usuario_expiracao (usuario_id, expira_em)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transacoes (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT UNSIGNED NOT NULL,
    descricao VARCHAR(160) NOT NULL,
    valor DECIMAL(12, 2) NOT NULL,
    tipo ENUM('receita', 'despesa') NOT NULL,
    data_transacao DATE NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transacoes_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT chk_transacoes_valor CHECK (valor > 0),
    INDEX idx_transacoes_usuario_data (usuario_id, data_transacao, id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS metas (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT UNSIGNED NOT NULL,
    nome_meta VARCHAR(120) NOT NULL,
    valor_alvo DECIMAL(12, 2) NOT NULL,
    valor_atual DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    data_limite DATE NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_metas_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT chk_metas_alvo CHECK (valor_alvo > 0),
    CONSTRAINT chk_metas_atual CHECK (valor_atual >= 0),
    INDEX idx_metas_usuario_prazo (usuario_id, data_limite, id)
) ENGINE=InnoDB;
