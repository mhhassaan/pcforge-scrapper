# Core configurations and metadata maps for all 7 component categories in the ETL pipeline

CATEGORIES = {
    "case": {
        "spec_table": "case_specs",
        "csv_patterns": ["scraped_data/**/case.csv"],
        "master_csv": "consolidated_cases_pcpp_style.csv",
        "fields": [
            "case_form_factor", "supported_motherboard_form_factors", "max_gpu_length_mm",
            "max_cpu_cooler_height_mm", "expansion_slots", "internal_3_5_bays",
            "internal_2_5_bays", "has_transparent_side_panel", "side_panel_type",
            "supported_psu_form_factors", "width_mm", "height_mm", "depth_mm"
        ],
        "types": {
            "max_gpu_length_mm": "int",
            "max_cpu_cooler_height_mm": "int",
            "expansion_slots": "int",
            "internal_3_5_bays": "int",
            "internal_2_5_bays": "int",
            "width_mm": "int",
            "height_mm": "int",
            "depth_mm": "int",
            "has_transparent_side_panel": "bool",
            "supported_motherboard_form_factors": "list",
            "supported_psu_form_factors": "list"
        },
        "description": "PC Case",
        "guidelines": """
        - case_form_factor: 'ATX Mid Tower', 'ATX Full Tower', 'MicroATX Mini Tower', 'Mini ITX Tower', etc.
        - supported_motherboard_form_factors: list of strings (e.g., ["ATX", "Micro ATX", "Mini ITX"])
        - max_gpu_length_mm: integer
        - max_cpu_cooler_height_mm: integer
        - expansion_slots: integer
        - internal_3_5_bays: integer
        - internal_2_5_bays: integer
        - has_transparent_side_panel: boolean
        - side_panel_type: 'Tempered Glass', 'Acrylic', 'None'
        - supported_psu_form_factors: list of strings (e.g., ["ATX", "SFX"])
        - width_mm: integer
        - height_mm: integer
        - depth_mm: integer
        """
    },
    "psu": {
        "spec_table": "psu_specs",
        "csv_patterns": ["scraped_data/**/psu.csv"],
        "master_csv": "consolidated_psu_pcpp_style.csv",
        "fields": [
            "wattage", "form_factor", "efficiency_rating", "modular", "length_mm",
            "fanless", "atx_24_pin", "eps_8_pin", "pcie_6_plus_2_pin", "pcie_12vhpwr",
            "sata_connectors", "molex_connectors"
        ],
        "types": {
            "wattage": "int",
            "length_mm": "int",
            "atx_24_pin": "int",
            "eps_8_pin": "int",
            "pcie_6_plus_2_pin": "int",
            "pcie_12vhpwr": "int",
            "sata_connectors": "int",
            "molex_connectors": "int",
            "modular": "bool",
            "fanless": "bool"
        },
        "description": "Power Supply Unit (PSU)",
        "guidelines": """
        - wattage: integer (e.g., 550, 650, 750, 850, 1000)
        - form_factor: 'ATX', 'SFX', 'SFX-L', 'TFX'
        - efficiency_rating: '80+ White', '80+ Bronze', '80+ Silver', '80+ Gold', '80+ Platinum', '80+ Titanium'
        - modular: boolean (True if Fully or Semi Modular, False if Non-Modular)
        - length_mm: integer (e.g., 140, 150, 160)
        - fanless: boolean
        - atx_24_pin: integer (usually 1)
        - eps_8_pin: integer (e.g., 1, 2)
        - pcie_6_plus_2_pin: integer (e.g., 2, 4, 6)
        - pcie_12vhpwr: integer (e.g., 0, 1)
        - sata_connectors: integer (e.g., 6, 8, 12)
        - molex_connectors: integer (e.g., 2, 4)
        """
    },
    "storage": {
        "spec_table": "storage_specs",
        "csv_patterns": ["scraped_data/**/ssd.csv", "scraped_data/**/hdd.csv", "scraped_data/**/nvme.csv"],
        "master_csv": "consolidated_storage_pcpp_style.csv",
        "fields": ["storage_type", "capacity_gb", "form_factor", "interface", "nvme"],
        "types": {
            "capacity_gb": "int",
            "nvme": "bool"
        },
        "description": "Storage Drive (SSD/HDD/NVMe)",
        "guidelines": """
        - storage_type: 'SSD' or 'HDD'
        - capacity_gb: integer (e.g., 250, 500, 1000, 2000, 4000). Note: 1TB = 1000, 2TB = 2000.
        - form_factor: 'M.2-2280', '2.5"', '3.5"', 'mSATA'
        - interface: 'PCIe 4.0 x4', 'PCIe 3.0 x4', 'SATA 6.0 Gb/s', 'PCIe 5.0 x4'
        - nvme: boolean (True if it's an NVMe drive, False for SATA SSDs and HDDs)
        """
    },
    "cpu": {
        "spec_table": "cpu_specs",
        "csv_patterns": ["scraped_data/**/cpu.csv"],
        "master_csv": "consolidated_cpus_pcpp_style.csv",
        "fields": [
            "socket", "cores", "threads", "base_clock_ghz", "boost_clock_ghz",
            "tdp_watts", "integrated_graphics", "lithography"
        ],
        "types": {
            "cores": "int",
            "threads": "int",
            "tdp_watts": "int",
            "base_clock_ghz": "float",
            "boost_clock_ghz": "float"
        },
        "description": "Processor (CPU)",
        "guidelines": """
        - socket: 'AM4', 'AM5', 'LGA1700', 'LGA1200', 'LGA1151', etc.
        - cores: integer (e.g., 6, 8, 12, 16, 24)
        - threads: integer (e.g., 12, 16, 20, 24, 32)
        - base_clock_ghz: float (e.g., 3.5, 3.8, 4.4)
        - boost_clock_ghz: float (e.g., 4.2, 4.8, 5.4, 5.7)
        - tdp_watts: integer (e.g., 65, 105, 125, 170)
        - integrated_graphics: Name of GPU if present (e.g., 'Radeon Graphics', 'Intel UHD Graphics 770') or 'None'
        - lithography: technology node (e.g., '5 nm', '7 nm', '10 nm', 'Intel 7')
        """
    },
    "gpu": {
        "spec_table": "gpu_specs",
        "csv_patterns": ["scraped_data/**/gpu.csv"],
        "master_csv": "consolidated_gpus_pcpp_style.csv",
        "fields": [
            "chipset_manufacturer", "chipset", "vram_gb", "memory_type", "core_base_clock_mhz",
            "core_boost_clock_mhz", "memory_bus_bit", "interface", "length_mm", "slot_width",
            "tdp_watts", "pcie_6_pin", "pcie_8_pin", "pcie_12vhpwr", "cooling", "hdmi_2_1",
            "displayport_2_1", "displayport_2_1a"
        ],
        "types": {
            "vram_gb": "int",
            "core_base_clock_mhz": "int",
            "core_boost_clock_mhz": "int",
            "memory_bus_bit": "int",
            "length_mm": "int",
            "slot_width": "int",
            "tdp_watts": "int",
            "pcie_6_pin": "int",
            "pcie_8_pin": "int",
            "pcie_12vhpwr": "int",
            "hdmi_2_1": "int",
            "displayport_2_1": "int",
            "displayport_2_1a": "int"
        },
        "description": "Graphics Card (GPU)",
        "guidelines": """
        - chipset_manufacturer: 'NVIDIA', 'AMD', 'Intel'
        - chipset: 'GeForce RTX 4070 SUPER', 'Radeon RX 7800 XT', 'GeForce RTX 3060', etc.
        - vram_gb: integer (e.g., 8, 12, 16, 24)
        - memory_type: 'GDDR6', 'GDDR6X', 'HBM2', etc.
        - core_base_clock_mhz: integer
        - core_boost_clock_mhz: integer
        - memory_bus_bit: integer (e.g., 128, 192, 256, 384)
        - interface: 'PCIe 4.0 x16', 'PCIe 4.0 x8', 'PCIe 3.0 x16'
        - length_mm: integer length of card (e.g. 242, 310)
        - slot_width: integer width in slots (e.g., 2, 3)
        - tdp_watts: integer (e.g., 130, 200, 220, 250, 450)
        - pcie_6_pin: integer count (usually 0, 1)
        - pcie_8_pin: integer count (usually 0, 1, 2, 3)
        - pcie_12vhpwr: integer count (usually 0, 1)
        - cooling: 'Single Fan', 'Dual Fan', 'Triple Fan', 'Liquid Cooled'
        - hdmi_2_1: integer count
        - displayport_2_1: integer count
        - displayport_2_1a: integer count
        """
    },
    "motherboard": {
        "spec_table": "motherboard_specs",
        "csv_patterns": ["scraped_data/**/motherboard.csv"],
        "master_csv": "consolidated_motherboards_pcpp_style.csv",
        "fields": [
            "socket", "chipset", "form_factor", "ram_type", "ram_slots", "max_ram_gb",
            "pcie_x16_slots", "pcie_x1_slots", "m2_slots", "sata_6gb_ports",
            "onboard_ethernet_gbps", "ecc_support", "raid_support"
        ],
        "types": {
            "ram_slots": "int",
            "max_ram_gb": "int",
            "pcie_x16_slots": "int",
            "pcie_x1_slots": "int",
            "m2_slots": "int",
            "sata_6gb_ports": "int",
            "onboard_ethernet_gbps": "float",
            "ecc_support": "bool",
            "raid_support": "bool"
        },
        "description": "Motherboard",
        "guidelines": """
        - socket: 'AM4', 'AM5', 'LGA1700', 'LGA1200', 'LGA1851', etc.
        - chipset: 'B650', 'B760', 'X670E', 'Z790', 'A520', etc.
        - form_factor: 'ATX', 'Micro ATX', 'Mini ITX', 'E-ATX'
        - ram_type: 'DDR4', 'DDR5'
        - ram_slots: integer (usually 2 or 4)
        - max_ram_gb: integer (e.g., 64, 128, 192, 256)
        - pcie_x16_slots: integer (usually 1, 2, 3)
        - pcie_x1_slots: integer
        - m2_slots: integer
        - sata_6gb_ports: integer (usually 4, 6)
        - onboard_ethernet_gbps: float (e.g. 1.0, 2.5, 10.0)
        - ecc_support: boolean
        - raid_support: boolean
        """
    },
    "ram": {
        "spec_table": "ram_specs",
        "csv_patterns": ["scraped_data/**/ram.csv"],
        "master_csv": "consolidated_ram_pcpp_style.csv",
        "fields": [
            "ram_type", "total_capacity_gb", "module_count", "module_capacity_gb",
            "speed_mhz", "cas_latency", "ecc", "registered", "form_factor",
            "voltage", "rgb", "heat_spreader"
        ],
        "types": {
            "total_capacity_gb": "int",
            "module_count": "int",
            "module_capacity_gb": "int",
            "speed_mhz": "int",
            "cas_latency": "int",
            "ecc": "bool",
            "registered": "bool",
            "rgb": "bool",
            "heat_spreader": "bool",
            "voltage": "float"
        },
        "description": "RAM (Memory)",
        "guidelines": """
        - ram_type: 'DDR4', 'DDR5', 'DDR3'
        - total_capacity_gb: integer total capacity of the kit (e.g., 8, 16, 32, 64, 96)
        - module_count: integer count of RAM sticks in kit (e.g., 1, 2, 4)
        - module_capacity_gb: integer capacity of a single stick (e.g., 8, 16, 32, 48)
        - speed_mhz: integer frequency (e.g., 3200, 3600, 5200, 5600, 6000)
        - cas_latency: integer CAS Latency (e.g. 16, 18, 30, 36, 40)
        - ecc: boolean
        - registered: boolean
        - form_factor: '288-pin DIMM' (desktop) or '262-pin SO-DIMM' (laptop) or 'SO-DIMM'
        - voltage: float (e.g., 1.2, 1.35, 1.4)
        - rgb: boolean
        - heat_spreader: boolean
        """
    }
}
