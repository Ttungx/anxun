-- 安巡系统完整演示数据导入脚本 (MySQL版本)
-- 基于demo_data.json的完整数据结构创建表并插入所有数据

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS anxun_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE anxun_demo;

-- 1. 创建分析结果表
CREATE TABLE IF NOT EXISTS analysis_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    risk_level VARCHAR(20) NOT NULL COMMENT '风险等级',
    summary TEXT NOT NULL COMMENT '分析摘要',
    detailed_analysis TEXT COMMENT '详细分析',
    analysis_time DATETIME COMMENT '分析时间',
    total_packets_analyzed INT DEFAULT 0 COMMENT '分析的数据包总数',
    analysis_duration VARCHAR(50) COMMENT '分析耗时',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 创建威胁表
CREATE TABLE IF NOT EXISTS threats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    threat_description TEXT NOT NULL COMMENT '威胁描述',
    severity VARCHAR(20) DEFAULT 'medium' COMMENT '严重程度',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 3. 创建建议表
CREATE TABLE IF NOT EXISTS recommendations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    recommendation TEXT NOT NULL COMMENT '安全建议',
    priority VARCHAR(20) DEFAULT 'medium' COMMENT '优先级',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 4. 创建学生信息表
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) UNIQUE NOT NULL COMMENT '学号',
    student_name VARCHAR(100) NOT NULL COMMENT '姓名',
    phone VARCHAR(20) COMMENT '电话',
    dormitory VARCHAR(100) COMMENT '宿舍',
    department VARCHAR(100) COMMENT '学院',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 创建高风险IP表
CREATE TABLE IF NOT EXISTS high_risk_ips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    ip_address VARCHAR(45) NOT NULL COMMENT 'IP地址',
    student_id VARCHAR(20) COMMENT '学号',
    risk_level VARCHAR(20) NOT NULL COMMENT '风险等级',
    threat_type VARCHAR(100) NOT NULL COMMENT '威胁类型',
    last_activity DATETIME COMMENT '最后活动时间',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL
);

-- 6. 创建统计数据表
CREATE TABLE IF NOT EXISTS traffic_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    total_high_risk_ips INT DEFAULT 0 COMMENT '高风险IP总数',
    total_medium_risk_ips INT DEFAULT 0 COMMENT '中风险IP总数',
    total_students_involved INT DEFAULT 0 COMMENT '涉及学生总数',
    total_packets_analyzed INT DEFAULT 0 COMMENT '分析数据包总数',
    analysis_duration VARCHAR(50) COMMENT '分析耗时',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 7. 创建协议分布表
CREATE TABLE IF NOT EXISTS protocol_distribution (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    protocol_name VARCHAR(20) NOT NULL COMMENT '协议名称',
    percentage DECIMAL(5,2) NOT NULL COMMENT '占比百分比',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 8. 创建数据包大小分布表
CREATE TABLE IF NOT EXISTS packet_size_distribution (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    size_range VARCHAR(20) NOT NULL COMMENT '大小范围',
    packet_count INT NOT NULL COMMENT '数据包数量',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 9. 创建源IP统计表
CREATE TABLE IF NOT EXISTS source_ip_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    ip_address VARCHAR(45) NOT NULL COMMENT 'IP地址',
    packet_count INT NOT NULL COMMENT '数据包数量',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 10. 创建连接统计表
CREATE TABLE IF NOT EXISTS top_connections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT,
    src_ip VARCHAR(45) NOT NULL COMMENT '源IP',
    dst_ip VARCHAR(45) NOT NULL COMMENT '目标IP',
    protocol VARCHAR(20) NOT NULL COMMENT '协议',
    port INT NOT NULL COMMENT '端口',
    packets INT NOT NULL COMMENT '数据包数',
    bytes BIGINT NOT NULL COMMENT '字节数',
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

-- 插入演示数据

-- 插入分析结果
INSERT INTO analysis_results (
    risk_level, 
    summary, 
    detailed_analysis, 
    analysis_time, 
    total_packets_analyzed, 
    analysis_duration
) VALUES (
    '高',
    '检测到校园网络中存在多种安全威胁，包括电信诈骗、刷单、恶意软件通信、异常流量模式等。涉及15个高风险IP地址和多个学院的学生，其中非计算机专业学生多涉及电信诈骗相关行为，计算机专业学生多涉及技术性攻击行为。建议立即采取综合性安全措施。',
    '通过对校园网络流量的深入分析和行为建模，发现了多个严重的安全问题。分析显示，IP地址192.168.1.105、10.0.2.88和172.16.3.42等表现出明显的恶意软件通信特征，频繁与已知恶意域名和C&C服务器进行通信。检测到来自多个IP的异常大流量传输，可能涉及敏感数据泄露和非法数据窃取。此外，发现大量IP地址参与P2P文件共享，严重违反了校园网络使用政策。最令人担忧的是检测到针对校园网络基础设施的系统性扫描和探测活动，以及潜在的DDoS攻击准备行为，需要立即采取全面的防护措施。',
    '2024-01-15 18:00:00',
    45892,
    '2分30秒'
);

SET @analysis_id = LAST_INSERT_ID();

-- 插入威胁数据
INSERT INTO threats (analysis_id, threat_description, severity) VALUES 
(@analysis_id, '检测到大量电信诈骗相关流量，包括虚假投资平台访问', 'high'),
(@analysis_id, '发现刷单、兼职诈骗等网络诈骗行为', 'high'),
(@analysis_id, '识别到恶意软件C&C通信和僵尸网络活动', 'high'),
(@analysis_id, '检测到异常大流量数据传输和潜在数据窃取', 'high'),
(@analysis_id, '发现大量P2P文件共享活动，违反校园网络政策', 'medium'),
(@analysis_id, '检测到潜在的DDoS攻击流量和网络扫描', 'high'),
(@analysis_id, '发现未授权的网络扫描行为和端口探测', 'medium'),
(@analysis_id, '检测到可疑的加密流量和异常连接模式', 'medium');

-- 插入建议数据
INSERT INTO recommendations (analysis_id, recommendation, priority) VALUES 
(@analysis_id, '立即隔离高风险IP地址并通知相关学生', 'high'),
(@analysis_id, '加强网络访问控制策略和实时监控', 'high'),
(@analysis_id, '部署入侵检测系统和威胁情报分析', 'high'),
(@analysis_id, '对涉及学生进行紧急安全教育和约谈', 'high'),
(@analysis_id, '定期更新安全策略和防护规则', 'medium'),
(@analysis_id, '建立学生网络行为监控和预警机制', 'medium'),
(@analysis_id, '加强宿舍网络准入控制和身份认证', 'medium');

-- 插入学生信息
INSERT INTO students (student_id, student_name, phone, dormitory, department) VALUES 
('2021120301', '陈志强', '13912345678', '梧桐苑1号楼201', '经济管理学院'),
('2022050102', '李雨婷', '13823456789', '梧桐苑2号楼305', '外国语学院'),
('2021080201', '王建华', '13734567890', '梧桐苑3号楼108', '网络工程学院'),
('2023030201', '张明轩', '13645678901', '梧桐苑1号楼412', '文学院'),
('2022080103', '刘思琪', '13556789012', '梧桐苑2号楼218', '电子信息工程学院'),
('2021130101', '赵文博', '13467890123', '梧桐苑3号楼325', '艺术学院'),
('2022090101', '孙雅琳', '13378901234', '梧桐苑4号楼301', '数据科学与大数据技术学院'),
('2021100101', '周俊杰', '13289012345', '梧桐苑4号楼402', '人工智能学院'),
('2023030101', '吴佳怡', '13190123456', '梧桐苑5号楼501', '法学院'),
('2021010102', '郑浩然', '13001234567', '梧桐苑5号楼502', '计算机科学与技术学院'),
('2022040101', '马欣然', '13912345670', '梧桐苑6号楼601', '教育学院'),
('2021110101', '冯立群', '13823456781', '梧桐苑6号楼602', '信息管理与信息系统学院'),
('2022060101', '许文静', '13734567892', '梧桐苑7号楼701', '化学与材料工程学院'),
('2021020101', '谢志伟', '13645678903', '梧桐苑7号楼702', '软件工程学院'),
('2023070101', '韩美玲', '13556789014', '梧桐苑8号楼801', '生物科学学院');

-- 插入高风险IP数据
INSERT INTO high_risk_ips (analysis_id, ip_address, student_id, risk_level, threat_type, last_activity) VALUES 
(@analysis_id, '192.168.1.105', '2021120301', '高', '电信诈骗', '2024-01-15 14:30:25'),
(@analysis_id, '192.168.2.88', '2022050102', '高', '刷单诈骗', '2024-01-16 09:45:12'),
(@analysis_id, '192.168.3.42', '2021080201', '高', '异常流量传输', '2024-01-15 16:20:08'),
(@analysis_id, '192.168.4.156', '2023030201', '中', '虚假投资平台', '2024-01-16 13:15:33'),
(@analysis_id, '192.168.5.77', '2022080103', '中', '网络扫描行为', '2024-01-15 17:05:41'),
(@analysis_id, '192.168.6.99', '2021130101', '中', '兼职诈骗', '2024-01-16 12:40:17'),
(@analysis_id, '192.168.7.88', '2022090101', '高', '僵尸网络', '2024-01-15 18:22:45'),
(@analysis_id, '192.168.8.123', '2021100101', '高', 'DDoS攻击', '2024-01-16 19:10:29'),
(@analysis_id, '192.168.9.55', '2023030101', '中', '网络赌博', '2024-01-16 11:25:14'),
(@analysis_id, '192.168.10.77', '2021010102', '高', '数据窃取', '2024-01-15 20:45:38'),
(@analysis_id, '192.168.11.201', '2022040101', '中', 'P2P文件共享', '2024-01-16 21:12:55'),
(@analysis_id, '192.168.12.145', '2021110101', '高', '恶意扫描', '2024-01-15 22:33:42'),
(@analysis_id, '192.168.13.88', '2022060101', '中', '虚假购物', '2024-01-16 09:47:21'),
(@analysis_id, '192.168.14.33', '2021020101', '高', '恶意软件通信', '2024-01-15 23:18:16'),
(@analysis_id, '192.168.15.66', '2023070101', '中', '贷款诈骗', '2024-01-16 08:52:39');

-- 插入统计数据
INSERT INTO traffic_statistics (analysis_id, total_high_risk_ips, total_medium_risk_ips, total_students_involved, total_packets_analyzed, analysis_duration) VALUES 
(@analysis_id, 8, 7, 15, 45892, '2分30秒');

-- 插入协议分布数据
INSERT INTO protocol_distribution (analysis_id, protocol_name, percentage) VALUES 
(@analysis_id, 'HTTPS', 32.5),
(@analysis_id, 'HTTP', 28.7),
(@analysis_id, 'TCP', 18.3),
(@analysis_id, 'UDP', 12.8),
(@analysis_id, 'DNS', 4.2),
(@analysis_id, 'ICMP', 1.8),
(@analysis_id, 'FTP', 0.9),
(@analysis_id, 'SSH', 0.5),
(@analysis_id, '其他', 0.3);

-- 插入数据包大小分布数据
INSERT INTO packet_size_distribution (analysis_id, size_range, packet_count) VALUES 
(@analysis_id, '0-100', 8456),
(@analysis_id, '100-500', 12823),
(@analysis_id, '500-1000', 9947),
(@analysis_id, '1000-1500', 8521),
(@analysis_id, '1500+', 6145);

-- 插入源IP统计数据
INSERT INTO source_ip_stats (analysis_id, ip_address, packet_count) VALUES 
(@analysis_id, '192.168.1.105', 3247),
(@analysis_id, '192.168.3.42', 2841),
(@analysis_id, '192.168.2.88', 2156),
(@analysis_id, '192.168.7.88', 1943),
(@analysis_id, '192.168.8.123', 1678),
(@analysis_id, '192.168.4.156', 1543),
(@analysis_id, '192.168.10.77', 1312),
(@analysis_id, '192.168.12.145', 1156),
(@analysis_id, '192.168.9.55', 989),
(@analysis_id, '192.168.14.33', 812),
(@analysis_id, '192.168.5.77', 756),
(@analysis_id, '192.168.6.99', 634),
(@analysis_id, '192.168.11.201', 578),
(@analysis_id, '192.168.13.88', 489),
(@analysis_id, '192.168.15.66', 423);

-- 插入连接统计数据
INSERT INTO top_connections (analysis_id, src_ip, dst_ip, protocol, port, packets, bytes) VALUES 
(@analysis_id, '192.168.1.105', '203.119.25.15', 'TCP', 443, 3247, 8924560),
(@analysis_id, '192.168.3.42', '185.199.108.153', 'HTTPS', 443, 2841, 15678900),
(@analysis_id, '192.168.2.88', '8.8.8.8', 'UDP', 53, 2156, 456320),
(@analysis_id, '192.168.7.88', '45.33.32.156', 'TCP', 6667, 1943, 5242880),
(@analysis_id, '192.168.8.123', '172.217.160.142', 'UDP', 53, 1678, 1048576),
(@analysis_id, '192.168.4.156', '104.16.249.249', 'HTTP', 80, 1543, 2345670),
(@analysis_id, '192.168.10.77', '198.51.100.42', 'HTTPS', 443, 1312, 4194304),
(@analysis_id, '192.168.12.145', '192.168.1.1', 'TCP', 22, 1156, 123450),
(@analysis_id, '192.168.9.55', '74.125.224.72', 'HTTPS', 443, 989, 3145728),
(@analysis_id, '192.168.14.33', '91.121.90.224', 'TCP', 8080, 812, 2097152);

-- 创建索引以提高查询性能
CREATE INDEX idx_high_risk_ips_ip ON high_risk_ips(ip_address);
CREATE INDEX idx_high_risk_ips_student ON high_risk_ips(student_id);
CREATE INDEX idx_high_risk_ips_risk_level ON high_risk_ips(risk_level);
CREATE INDEX idx_students_department ON students(department);
CREATE INDEX idx_threats_severity ON threats(severity);
CREATE INDEX idx_recommendations_priority ON recommendations(priority);

-- 创建视图方便查询
CREATE VIEW security_dashboard AS
SELECT 
    ar.id as analysis_id,
    ar.risk_level,
    ar.summary,
    ar.analysis_time,
    ts.total_high_risk_ips,
    ts.total_medium_risk_ips,
    ts.total_students_involved,
    ts.total_packets_analyzed,
    ts.analysis_duration,
    COUNT(DISTINCT t.id) as threat_count,
    COUNT(DISTINCT r.id) as recommendation_count
FROM analysis_results ar
LEFT JOIN traffic_statistics ts ON ar.id = ts.analysis_id
LEFT JOIN threats t ON ar.id = t.analysis_id
LEFT JOIN recommendations r ON ar.id = r.analysis_id
GROUP BY ar.id, ts.id;

CREATE VIEW student_risk_summary AS
SELECT 
    s.student_id,
    s.student_name,
    s.department,
    s.dormitory,
    h.ip_address,
    h.risk_level,
    h.threat_type,
    h.last_activity
FROM students s
JOIN high_risk_ips h ON s.student_id = h.student_id
ORDER BY 
    CASE h.risk_level 
        WHEN '高' THEN 1 
        WHEN '中' THEN 2 
        ELSE 3 
    END,
    h.last_activity DESC;

CREATE VIEW department_risk_stats AS
SELECT 
    s.department,
    COUNT(*) as total_students,
    SUM(CASE WHEN h.risk_level = '高' THEN 1 ELSE 0 END) as high_risk_count,
    SUM(CASE WHEN h.risk_level = '中' THEN 1 ELSE 0 END) as medium_risk_count,
    ROUND(SUM(CASE WHEN h.risk_level = '高' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as high_risk_percentage
FROM students s
JOIN high_risk_ips h ON s.student_id = h.student_id
GROUP BY s.department
ORDER BY high_risk_count DESC;

-- 查询验证数据
SELECT '=== 安全仪表板总览 ===' as info;
SELECT * FROM security_dashboard;

SELECT '=== 学生风险汇总 ===' as info;
SELECT * FROM student_risk_summary LIMIT 10;

SELECT '=== 学院风险统计 ===' as info;
SELECT * FROM department_risk_stats;

SELECT '=== 协议分布 ===' as info;
SELECT protocol_name, percentage FROM protocol_distribution ORDER BY percentage DESC;

SELECT '=== 威胁类型统计 ===' as info;
SELECT threat_type, COUNT(*) as count, risk_level 
FROM high_risk_ips 
GROUP BY threat_type, risk_level 
ORDER BY count DESC;

SELECT '=== 数据导入完成 ===' as info;
SELECT 
    (SELECT COUNT(*) FROM students) as '学生总数',
    (SELECT COUNT(*) FROM high_risk_ips) as '高风险IP总数',
    (SELECT COUNT(*) FROM threats) as '威胁总数',
    (SELECT COUNT(*) FROM recommendations) as '建议总数',
    (SELECT COUNT(*) FROM protocol_distribution) as '协议类型数',
    (SELECT COUNT(*) FROM top_connections) as '连接记录数';