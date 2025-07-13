## 实现逻辑
调用ollama的pai来提供模型服务，模型型号为qwen3:8b
如果前端上传了流量文件，那么就走分析流量这一块，结构化输出，摘要显示在出在前端的模型对话页面，给出应对策略，同时将流量分析的结构化输出结果可视化展示在流量分析页面，如果没有上传文件就走正常交互。
对于上传的流量文件，参考下方的代码来实现文件的读取和上传：
``` python
import os
import subprocess

def load_pcap(pcap_file):
    build_data = []
    tmp_path = "tmp.txt"

    # 删除旧的 tmp.txt（如果存在）
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    fields = ["frame.encap_type", "frame.time", "frame.offset_shift", "frame.time_epoch", "frame.time_delta",
              "frame.time_relative", "frame.number", "frame.len", "frame.marked", "frame.protocols", "eth.dst",
              "eth.dst_resolved", "eth.src", "eth.src_resolved", "eth.type",
              "ip.version", "ip.hdr_len", "ip.dsfield", "ip.dsfield.dscp", "ip.len", "ip.id",
              "ip.flags", "ip.flags.rb", "ip.flags.df", "ip.flags.mf", "ip.frag_offset", "ip.ttl", "ip.proto",
              "ip.checksum", "ip.checksum.status", "tcp.srcport", "tcp.dstport", "tcp.stream",
              "tcp.len", "tcp.seq", "tcp.nxtseq", "tcp.ack", "tcp.hdr_len", "tcp.flags",
              "tcp.flags.res", "tcp.flags.cwr", "tcp.flags.urg", "tcp.flags.ack",
              "tcp.flags.push", "tcp.flags.reset", "tcp.flags.syn", "tcp.flags.fin", "tcp.flags.str",
              "tcp.window_size", "tcp.window_size_scalefactor", "tcp.checksum", "tcp.checksum.status",
              "tcp.urgent_pointer",
              "tcp.time_relative", "tcp.time_delta", "tcp.analysis.bytes_in_flight", "tcp.analysis.push_bytes_sent",
              "tcp.segment",
              "tcp.segment.count", "tcp.reassembled.length", "tcp.payload", "udp.srcport", "udp.dstport", "udp.length",
              "udp.checksum", "udp.checksum.status", "udp.stream", "data.len"]

    fields_part = " ".join(f"-e {field}" for field in fields)
    cmd = f'tshark -r "{pcap_file}" {fields_part} -T fields -Y "tcp or udp" > "{tmp_path}"'

    print("Running command:")
    print(cmd)

    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        print(f"[ERROR] Tshark failed with exit code {proc.returncode}")
        print(f"[STDERR]:\n{stderr.decode('utf-8', errors='ignore')}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return ""

    if not os.path.exists(tmp_path):
        print("[ERROR] tmp.txt was not created.")
        return ""

    with open(tmp_path, "r", encoding="utf-8", errors="ignore") as fin:
        lines = fin.readlines()
        print(f"\n[INFO] Read {len(lines)} packets from tmp.txt")

    for line in lines:
        packet_data = ""
        values = line.strip('\n').split("\t")

        if not values or values == ['']:
            continue

        packet_data += fields[0] + ": " + values[0]
        for field, value in zip(fields[1:], values[1:]):
            if field == "tcp.flags.str":
                value = value.encode("unicode_escape").decode("unicode_escape")
            if field == "tcp.payload":
                value = value[:1000] if len(value) > 1000 else value
            if value == "":
                continue
            packet_data += ", "
            packet_data += field + ": " + value

        build_data.append(packet_data)

    if not build_data:
        print("[INFO] No data extracted from tmp.txt")
        return ""

    print("\n[SUCCESS] First packet parsed result:")
    return build_data[0]

# === 主程序入口 ===
if __name__ == "__main__":
    data = load_pcap("永恒之蓝.pcap")
    print(data)
```
处理数据时要注意截断，避免撑爆模型的上下文
模型对话要尽可能实现流式对话，通过提示词工程等优化模型的输出。
流量的捕获使用tshark或者pyshark来获取，哪个方便你用哪个，要设置捕获流量的时限，不能太多

与模型的对话不能是每次都是单次api的调用，这样没有实现记忆功能

流量捕获之后直接提取流量包的内容，写入一个文件中然后上传给ai
除了流量捕获之外也可以直接上传流量，让ai来完成流量分析的功能