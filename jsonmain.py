import time
import os
import json
import logging
import threading
import socket
from mne_network_node import MNETheorizedNetworkNode

# Configure supervisor logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] (Supervisor-Core): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class TelemetryLedgerAnalyzer:
    """
    Supervises the execution of the MNE Network Node, monitors UDP packet broadcasts,
    and analyzes the persistent JSONL ledger file post-execution.
    """
    def __init__(self, ledger_filename="neural_telemetry_ledger.jsonl", listen_port=5005):
        self.ledger_filename = ledger_filename
        self.listen_port = listen_port
        self.packet_count = 0
        self.listening = threading.Event()

    def udp_listener_daemon(self):
        """Listens on the loopback network interface to verify live UDP packet transmission."""
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            listener_sock.bind(("127.0.0.1", self.listen_port))
            listener_sock.settimeout(1.0)
        except Exception as e:
            logging.warning(f"Could not bind listener socket to port {self.listen_port}: {e}")
            return

        self.listening.set()
        logging.info(f"UDP Telemetry Listener active on port {self.listen_port}...")

        while self.listening.is_set():
            try:
                data, addr = listener_sock.recvfrom(4096)
                self.packet_count += 1
                decoded_msg = data.decode('utf-8')
                logging.info(f"[UDP Intercept #{self.packet_count}] From {addr} -> Payload: {decoded_msg[:80]}...")
            except socket.timeout:
                continue
            except Exception:
                break

        listener_sock.close()
        logging.info("UDP Telemetry Listener safely shut down.")

    def analyze_ledger_report(self):
        """Parses and computes statistical summaries from the saved JSONL ledger file."""
        if not os.path.exists(self.ledger_filename):
            logging.warning(f"Ledger file '{self.ledger_filename}' not found for analysis.")
            return

        logging.info("==================================================")
        logging.info("       POST-EXECUTION LEDGER ANALYTICS REPORT     ")
        logging.info("==================================================")
        
        traces = []
        potentials = []
        record_count = 0

        with open(self.ledger_filename, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    record_count += 1
                    traces.append(record["tensor_trace"])
                    potentials.append(record["mean_potential_uv"])

        if record_count > 0:
            logging.info(f"Total Records Parsed:     {record_count}")
            logging.info(f"Mean Tensor Trace:        {sum(traces) / record_count:.6f}")
            logging.info(f"Peak Tensor Trace:        {max(traces):.6f}")
            logging.info(f"Minimum Tensor Trace:     {min(traces):.6f}")
            logging.info(f"Mean Neural Potential:    {sum(potentials) / record_count:.4f} uV")
            logging.info(f"Total UDP Packets Caught: {self.packet_count}")
        else:
            logging.info("Ledger file is empty.")
        
        logging.info("==================================================")

if __name__ == "__main__":
    ledger_file = "neural_telemetry_ledger.jsonl"
    
    # Clean up old ledger file from prior runs if desired
    if os.path.exists(ledger_file):
        os.remove(ledger_file)
        print(f"[{ledger_file}] Cleared previous ledger session.")

    print("\n--------------------------------------------------")
    print("  INITIALIZING MNE NETWORK NODE SUPERVISOR RUNNER ")
    print("--------------------------------------------------\n")

    supervisor = TelemetryLedgerAnalyzer(ledger_filename=ledger_file)

    # 1. Start the background UDP packet verification listener
    listener_thread = threading.Thread(target=supervisor.udp_listener_daemon, daemon=True)
    listener_thread.start()

    # 2. Instantiate and start the core MNE node from 'mne_network_node.py'
    node = MNETheorizedNetworkNode(ledger_filename=ledger_file)
    node_daemon = node.start()

    try:
        # Let the system run its continuous loop for 6 seconds for demonstration
        run_duration = 6
        logging.info(f"Supervisor active. Running MNE node orchestration for {run_duration} seconds...")
        time.sleep(run_duration)

    except KeyboardInterrupt:
        logging.info("Manual interrupt detected by supervisor.")

    finally:
        # 3. Graceful shutdown sequence
        logging.info("Initiating system shutdown sequence...")
        node.running.clear()
        supervisor.listening.clear()
        
        node_daemon.join(timeout=2.0)
        listener_thread.join(timeout=2.0)

        # 4. Generate post-execution analysis report
        supervisor.analyze_ledger_report()
        print("\n[Supervisor Execution Complete]")
      
