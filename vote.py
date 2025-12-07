import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os

# Configuration
ASSETS_DIR = "assets"
MEDIA_DIR = "media"

# DB Connection
import pymongo
from datetime import datetime
try:
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["election_portal_db"]
    candidates_collection = db["candidates_candidate"]
    vote_collection = db["vote"]
    print("Connected to MongoDB")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    candidates_collection = None
    vote_collection = None

def get_party_color(party_name):
    colors = {
        "SJB": "#008000", # Green
        "UNP": "#008000", # Green
        "SLPP": "#800000", # Maroon
        "NPP": "#cc0000", # Red
        "SLFP": "#0000FF", # Blue
        "Independent": "#808080" # Grey
    }
    return colors.get(party_name, "#666666")

# Fetch Candidates from DB
CANDIDATE_DATA = []
if candidates_collection is not None:
    try:
        # Find all candidates
        cursor = candidates_collection.find()
        for doc in cursor:
            c_id = str(doc["_id"])
            # Prefer ballot_name, fallback to full_name
            name = doc.get("ballot_name") or doc.get("full_name") or "Unknown"
            party = doc.get("party_name") or "Independent"
            image_path = doc.get("candidate_photo", "")
            
            CANDIDATE_DATA.append({
                "id": c_id,
                "name": name,
                "party": party,
                "color": get_party_color(party),
                "image": image_path
            })
        print(f"Loaded {len(CANDIDATE_DATA)} candidates from DB")
    except Exception as e:
        print(f"Error fetching candidates: {e}")

# If no candidates found (or DB error), add some placeholders for testing if needed
if not CANDIDATE_DATA:
    print("No candidates found in DB, using empty list.")

class VotingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Election Commission - Voting Interface")
        self.root.geometry("700x950") # Slightly larger window
        self.root.configure(bg="#fceefc") 

        # State
        self.preferences = {1: None, 2: None, 3: None} 
        self.candidate_buttons = {} 

        self.setup_ui()

    def setup_ui(self):
        # --- Header ---
        header_frame = tk.Frame(self.root, bg="#b30000", height=60) # Reduced height
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)
        
        # Centered Header Content
        header_content = tk.Frame(header_frame, bg="#b30000")
        header_content.pack(expand=True)
        
        home_icon = tk.Label(header_content, text="🏠", bg="#b30000", fg="white", font=("Segoe UI Emoji", 20))
        home_icon.pack(side="left", padx=15)
        
        header_title = tk.Label(header_content, text="Janaadhipathiwarana - 2024", bg="#b30000", fg="white", font=("Segoe UI", 16, "bold"))
        header_title.pack(side="left", pady=10)

        # Sub-header (Election Commission)
        sub_header = tk.Frame(self.root, bg="#ffe6f2", pady=5) # Reduced padding
        sub_header.pack(fill="x")
        
        tk.Label(sub_header, text="මැතිවරණ කොමිෂන් සභාව", bg="#ffe6f2", fg="#800080", font=("Iskoola Pota", 12, "bold")).pack()
        tk.Label(sub_header, text="தேர்தல் ஆணையம்", bg="#ffe6f2", fg="#4a004a", font=("Arial", 10)).pack()
        tk.Label(sub_header, text="Election Commission", bg="#ffe6f2", fg="#4a004a", font=("Arial", 10)).pack()

        # Color bar
        color_bar = tk.Frame(self.root, height=4)
        color_bar.pack(fill="x")
        colors = ["#008080", "#ff8c00", "#ffd700", "#800080"]
        for col in colors:
            f = tk.Frame(color_bar, bg=col, width=150)
            f.pack(side="left", fill="both", expand=True)

        # --- Main Content (Scrollable) ---
        # Using a canvas for scrolling
        main_container = tk.Frame(self.root, bg="#fceefc")
        main_container.pack(fill="both", expand=True, padx=10, pady=5) # Reduced padding

        canvas = tk.Canvas(main_container, bg="#fceefc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        
        # The frame inside the canvas
        self.scrollable_frame = tk.Frame(canvas, bg="#fceefc")

        # Configure the scroll region whenever the frame size changes
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Create window inside canvas
        # anchor="n" keeps it centered horizontally if we configure it right
        canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Ensure the frame expands to fill the canvas width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        canvas.bind("<Configure>", on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Candidate Grid
        self.create_candidate_grid()

        # --- Footer ---
        self.create_footer()

    def create_candidate_grid(self):
        columns = 4
        # Configure grid columns to have equal weight for centering
        for i in range(columns):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

        for index, candidate in enumerate(CANDIDATE_DATA):
            row = index // columns
            col = index % columns
            self.create_candidate_card(candidate, row, col)

    def create_candidate_card(self, candidate, row, col):
        # Card Container (Shadow effect using nested frames)
        shadow = tk.Frame(self.scrollable_frame, bg="#d0d0d0")
        shadow.grid(row=row, column=col, padx=8, pady=8, sticky="nsew") # Reduced padding
        
        card = tk.Frame(shadow, bg="white", bd=0, width=150, height=250) # Reduced height
        card.pack(padx=1, pady=1, fill="both", expand=True) # 1px padding for border effect
        card.pack_propagate(False)

        # Image Placeholder (Rounded look simulation)
        img_frame = tk.Frame(card, bg="#f0f0f0", width=120, height=90) # Reduced height
        img_frame.pack(pady=8)
        img_frame.pack_propagate(False)
        
        # Try to load image if exists, else text
        image_loaded = False
        if candidate.get("image"):
            try:
                # Construct absolute path to media
                # Assuming 'media' folder is in the same directory as this script or configured
                img_path = os.path.join(MEDIA_DIR, candidate["image"])
                if os.path.exists(img_path):
                    pil_img = Image.open(img_path)
                    # Resize to fit 120x90
                    pil_img = pil_img.resize((120, 90), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    
                    img_label = tk.Label(img_frame, image=tk_img, bg="#f0f0f0")
                    img_label.image = tk_img # Keep reference
                    img_label.pack(expand=True, fill="both")
                    image_loaded = True
            except Exception as e:
                print(f"Error loading image for {candidate['name']}: {e}")

        if not image_loaded:
            img_label = tk.Label(img_frame, text="👤", bg="#e0e0e0", fg="#888", font=("Segoe UI Emoji", 35))
            img_label.pack(expand=True, fill="both")

        # Name Label
        name_bg = candidate["color"]
        # Ensure text is readable against background
        text_fg = "white"
        
        name_frame = tk.Frame(card, bg=name_bg, height=35) # Reduced height
        name_frame.pack(fill="x", padx=10)
        name_frame.pack_propagate(False)
        
        name_label = tk.Label(name_frame, text=candidate["name"], bg=name_bg, fg=text_fg, 
                              wraplength=130, font=("Segoe UI", 9, "bold"))
        name_label.pack(expand=True, fill="both")

        # Party Label
        party_label = tk.Label(card, text=candidate["party"], bg="#f8f8f8", fg="#555", font=("Segoe UI", 8))
        party_label.pack(fill="x", padx=10, pady=4)

        # Buttons
        btn_frame = tk.Frame(card, bg="white")
        btn_frame.pack(pady=8, side="bottom")

        for i in range(1, 4):
            # Custom button style - Purple border for visibility
            btn = tk.Button(btn_frame, text=str(i), width=3, relief="solid", bg="white", bd=1,
                            fg="#800080", # Purple text
                            font=("Segoe UI", 10, "bold"),
                            cursor="hand2",
                            activebackground="#f0f0f0",
                            command=lambda r=i, c=candidate: self.select_preference(r, c))
            btn.pack(side="left", padx=5) # Increased padding
            
            # Store button reference
            self.candidate_buttons[(candidate["id"], i)] = btn
            
            # Ensure border is visible (Windows specific sometimes)
            # relief="solid" usually gives a black border, we can try to style it if needed
            # but standard tkinter is limited on border color without Frame hacks.
            # We will rely on relief="solid" and fg color for now.

    def create_footer(self):
        footer_frame = tk.Frame(self.root, bg="#ffe6f2", pady=15, bd=2, relief="raised")
        footer_frame.pack(fill="x", side="bottom")

        tk.Label(footer_frame, text="ඔබගේ මනාපයන් (Your Preferences):", bg="#ffe6f2", font=("Arial", 10, "bold")).pack(anchor="w", padx=20)

        # Container for Slots and Buttons (Horizontal Layout)
        footer_content = tk.Frame(footer_frame, bg="#ffe6f2")
        footer_content.pack(fill="x", padx=20, pady=10)

        # Selected Candidates Display (Left side)
        self.selection_display = tk.Frame(footer_content, bg="#ffe6f2")
        self.selection_display.pack(side="left")
        
        self.pref_slots = {}
        for i in range(1, 4):
            slot_frame = tk.Frame(self.selection_display, width=90, height=110, bg="white", bd=1, relief="solid")
            slot_frame.pack(side="left", padx=5) # Reduced gap between slots
            slot_frame.pack_propagate(False)
            
            # Rank Label
            rank_lbl = tk.Label(slot_frame, text=str(i), bg="#ddd", width=2)
            rank_lbl.pack(anchor="ne")

            lbl = tk.Label(slot_frame, text=f"Empty", bg="white", fg="#aaa")
            lbl.pack(expand=True)
            self.pref_slots[i] = lbl

        # Action Buttons (Right side of slots, but aligned left relative to the container)
        btn_frame = tk.Frame(footer_content, bg="#ffe6f2")
        btn_frame.pack(side="left", padx=30) # Gap between slots and buttons

        # Reset Button (Yellow/Gold)
        reset_btn = tk.Button(btn_frame, text="නැවත\nආරම්භ\nකරන්න", bg="#ffd700", fg="black", 
                              font=("Arial", 10, "bold"), command=self.reset_preferences, 
                              width=12, height=3, relief="raised", bd=3)
        reset_btn.pack(side="left", padx=10)

        # Confirm Button (Green)
        confirm_btn = tk.Button(btn_frame, text="තහවුරු කරන්න", bg="#00b33c", fg="white", 
                                font=("Arial", 12, "bold"), command=self.confirm_vote, 
                                width=20, height=3, relief="raised", bd=3)
        confirm_btn.pack(side="left", padx=10)

    def select_preference(self, rank, candidate):
        # Logic:
        # 1. If candidate is already selected in another rank, remove them from that rank.
        # 2. Assign candidate to new rank.
        
        # Check if candidate is already selected
        for r, c_id in list(self.preferences.items()):
            if c_id == candidate["id"]:
                self.preferences[r] = None
        
        # Assign to new rank
        self.preferences[rank] = candidate["id"]
        
        self.update_footer_display()
        self.update_button_styles()

    def reset_preferences(self):
        self.preferences = {1: None, 2: None, 3: None}
        self.update_footer_display()
        self.update_button_styles()

    def confirm_vote(self):
        # Basic validation
        if not any(self.preferences.values()):
            messagebox.showwarning("Warning", "Please select at least one preference.")
            return
        
        # Save to MongoDB
        if vote_collection is not None:
            try:
                vote_doc = {
                    "preferences": {str(k): v for k, v in self.preferences.items() if v}, # Store only selected
                    "timestamp": datetime.now()
                }
                vote_collection.insert_one(vote_doc)
                print("Vote saved to MongoDB")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save vote: {e}")
                return

        msg = "Votes:\n"
        for r in range(1, 4):
            c_id = self.preferences[r]
            if c_id:
                c_name = next((c["name"] for c in CANDIDATE_DATA if c["id"] == c_id), "None")
                msg += f"Preference {r}: {c_name}\n"
            
        messagebox.showinfo("Confirm Vote", "Vote Submitted Successfully!\n\n" + msg)
        self.reset_preferences()

    def update_footer_display(self):
        for r in range(1, 4):
            c_id = self.preferences[r]
            slot_label = self.pref_slots[r]
            
            if c_id:
                c_data = next((c for c in CANDIDATE_DATA if c["id"] == c_id), None)
                if c_data:
                    slot_label.config(text=c_data["name"], fg="black", font=("Arial", 8, "bold"), wraplength=70)
            else:
                slot_label.config(text=f"Empty", fg="#aaa", font=("Arial", 8))

    def update_button_styles(self):
        # Reset all buttons
        for (c_id, rank), btn in self.candidate_buttons.items():
            btn.config(bg="SystemButtonFace", fg="black") # Default look

        # Highlight selected
        colors = {1: "#800080", 2: "#008000", 3: "#800000"} # Purple, Green, Red
        
        for rank, c_id in self.preferences.items():
            if c_id:
                btn = self.candidate_buttons.get((c_id, rank))
                if btn:
                    btn.config(bg=colors.get(rank, "blue"), fg="white")

if __name__ == "__main__":
    root = tk.Tk()
    app = VotingApp(root)
    root.mainloop()
