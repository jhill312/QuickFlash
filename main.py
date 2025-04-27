import psycopg2
import streamlit as st
import bcrypt
import uuid

def connect_db():
    return psycopg2.connect(
        dbname="flashcards",
        user="postgres",
        password="password",
        host="localhost",
        port="5432"
    )

# ----- PASSWORD UTILITIES -----
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ----- DATABASE OPERATIONS -----
def add_user(username, email, password):
    conn = connect_db()
    cur = conn.cursor()
    hashed_pw = hash_password(password)
    try:
        cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email, hashed_pw))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False
    finally:
        conn.close()

def login_user(email, password):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT userID, password_hash FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    conn.close()

    if user and check_password(password, user[1]):
        return user[0]  
    else:
        return None

def show_login():
    st.subheader("🔐 Log In")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user_id = login_user(email, password)
        if user_id:
            st.success("Logged in successfully!")
            st.session_state['user_id'] = user_id
        else:
            st.error("Invalid credentials")

def show_signup():
    st.subheader("📋 Sign Up")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if add_user(username, email, password):
            st.success("Account created! Please log in.")
        else:
            st.error("Failed to create account. Maybe email is already used?")

def get_user_info(user_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT username, email FROM users WHERE userID = %s", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user if user else ("Unknown", "Unknown")

def create_flashcard_set(user_id, title, subject_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO flashcardset (title, userID, subjectID)
        VALUES (%s, %s, %s) RETURNING setID;
    """, (title, user_id, subject_id))
    set_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return set_id

def get_user_flashcard_sets(user_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT flashcardset.setID, flashcardset.title, subject.name
        FROM flashcardset
        JOIN subject ON flashcardset.subjectID = subject.subjectID
        WHERE flashcardset.userID = %s;
    """, (user_id,))
    sets = cur.fetchall()
    conn.close()
    return sets

def get_flashcards_in_set(set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT flashcard.cardID, flashcard.question, flashcard.answer
        FROM flashcard
        JOIN contains ON flashcard.cardID = contains.cardID
        WHERE contains.setID = %s;
    """, (set_id,))
    flashcards = cur.fetchall()
    conn.close()
    return flashcards

def add_flashcard_to_set(set_id, question, answer):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO flashcard (question, answer)
        VALUES (%s, %s) RETURNING cardID;
    """, (question, answer))
    card_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO contains (cardID, setID)
        VALUES (%s, %s);
    """, (card_id, set_id))
    conn.commit()
    conn.close()
    return card_id

def update_flashcard(card_id, question, answer):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE flashcard
        SET question = %s, answer = %s
        WHERE cardID = %s;
    """, (question, answer, card_id))
    conn.commit()
    conn.close()

def delete_flashcard(card_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM contains WHERE cardID = %s;", (card_id,))
    cur.execute("DELETE FROM flashcard WHERE cardID = %s;", (card_id,))
    conn.commit()
    conn.close()

def get_published_flashcard_sets():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT flashcardset.setID, flashcardset.title, subject.name, users.username
        FROM flashcardset
        JOIN subject ON flashcardset.subjectID = subject.subjectID
        JOIN users ON flashcardset.userID = users.userID
        WHERE flashcardset.published = TRUE;
    """)
    sets = cur.fetchall()
    conn.close()
    return sets

def set_flashcardset_published(set_id, published=True):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE flashcardset SET published = %s WHERE setID = %s", (published, set_id))
    conn.commit()
    conn.close()

def check_if_set_is_published(set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT published FROM flashcardset WHERE setID = %s", (set_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else False

def show_flashcard_viewer():
    set_id = st.session_state["viewing_set_id"]
    cards = get_flashcards_in_set(set_id)

    if not cards:
        st.warning("No cards in this set.")
        if st.button("⬅️ Back"):
            del st.session_state["viewing_set_id"]
            st.rerun()
        return

    idx = st.session_state.get("current_card", 0)
    card = cards[idx]
    question, answer = card[1], card[2]

    st.markdown("## 🃏 Flashcard Viewer")

    with st.container():
        st.markdown(
            f"""
            <div style='background-color:#f9f9f9;
                        padding:50px;
                        text-align:center;
                        border-radius:12px;
                        box-shadow:2px 2px 10px rgba(0,0,0,0.1);
                        font-size:24px;
                        min-height:200px;
                        color:#222;'>
                {answer if st.session_state.get("show_answer", False) else question}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Back"):
            del st.session_state["viewing_set_id"]
            st.rerun()

    with col2:
        if st.button("🔁 Flip"):
            st.session_state["show_answer"] = not st.session_state.get("show_answer", False)

    with col3:
        next_index = (idx + 1) % len(cards)
        if st.button("➡️ Next"):
            st.session_state["current_card"] = next_index
            st.session_state["show_answer"] = False
            st.rerun()
    
def show_review_flashcards():
    set_id = st.session_state["review_set_id"]
    user_id = st.session_state["user_id"]
    cards = get_flashcards_in_set(set_id)

    if not cards:
        st.warning("No flashcards in this set.")
        if st.button("⬅️ Back"):
            del st.session_state["review_set_id"]
            st.rerun()
        return

    
    if "review_queue" not in st.session_state:
        st.session_state["review_queue"] = cards.copy()
        st.session_state["review_index"] = 0
        st.session_state["review_show_answer"] = False
        initialize_progress(user_id, set_id, len(cards))

    queue = st.session_state["review_queue"]

    if not queue:
        st.success("🎉 You've completed this set!")
        if st.button("🔄 Reset Progress"):
            reset_progress(user_id, set_id)
            del st.session_state["review_queue"]
            del st.session_state["review_index"]
            del st.session_state["review_show_answer"]
            st.rerun()
        if st.button("⬅️ Back to menu"):
            del st.session_state["review_set_id"]
            st.rerun()
        return

    
    card = queue[st.session_state["review_index"]]
    card_id, question, answer = card

    
    completed, total = get_progress(user_id, set_id)
    st.progress(completed / total if total > 0 else 0)
    st.markdown(f"**Progress:** {completed} / {total}")

    
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Slab&display=swap');
        .review-card {
            font-family: 'Roboto Slab', serif;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class='review-card' style='
            background-color:#fff;
            padding:60px;
            text-align:center;
            border-radius:14px;
            font-size:30px;
            color:#222;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            min-height:220px;
            margin-bottom: 20px;
        '>
            {answer if st.session_state.get("review_show_answer", False) else question}
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔁 Flip"):
            st.session_state["review_show_answer"] = not st.session_state["review_show_answer"]

    with col2:
        if st.button("✅ I got it"):
            increment_progress(user_id, set_id)
            queue.pop(st.session_state["review_index"])
            st.session_state["review_index"] = 0
            st.session_state["review_show_answer"] = False
            st.rerun()

    with col3:
        if st.button("❌ I missed it"):
            missed_card = queue.pop(st.session_state["review_index"])
            queue.append(missed_card)  # Push to back
            st.session_state["review_index"] = 0
            st.session_state["review_show_answer"] = False
            st.rerun()

    if st.button("⬅️ Back to menu"):
        del st.session_state["review_set_id"]
        del st.session_state["review_queue"]
        del st.session_state["review_index"]
        del st.session_state["review_show_answer"]
        st.rerun()

def initialize_progress(user_id, set_id, total_cards):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO progress (userID, setID, completed_cards, total_cards)
        VALUES (%s, %s, 0, %s)
        ON CONFLICT (userID, setID) DO NOTHING;
    """, (user_id, set_id, total_cards))
    conn.commit()
    conn.close()

def get_progress(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT completed_cards, total_cards FROM progress
        WHERE userID = %s AND setID = %s;
    """, (user_id, set_id))
    result = cur.fetchone()
    conn.close()
    return result if result else (0, 0)

def increment_progress(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()

    
    cur.execute("""
        UPDATE progress
        SET completed_cards = completed_cards + 1
        WHERE userID = %s AND setID = %s AND completed_cards < total_cards;
    """, (user_id, set_id))
    
    conn.commit()
    conn.close()

def reset_progress(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE progress
        SET completed_cards = 0
        WHERE userID = %s AND setID = %s;
    """, (user_id, set_id))
    conn.commit()
    conn.close()

def copy_flashcard_set(original_set_id, new_owner_id):
    conn = connect_db()
    cur = conn.cursor()

    
    cur.execute("""
        SELECT title, subjectID FROM flashcardset WHERE setID = %s
    """, (original_set_id,))
    original = cur.fetchone()

    if not original:
        conn.close()
        return None

    title, subject_id = original
    new_title = f"{title} (Copy)"

    
    cur.execute("""
        INSERT INTO flashcardset (title, userID, subjectID, published)
        VALUES (%s, %s, %s, FALSE)
        RETURNING setID
    """, (new_title, new_owner_id, subject_id))
    new_set_id = cur.fetchone()[0]

    
    cur.execute("""
        SELECT flashcard.question, flashcard.answer
        FROM flashcard
        JOIN contains ON flashcard.cardID = contains.cardID
        WHERE contains.setID = %s
    """, (original_set_id,))
    cards = cur.fetchall()

    
    for question, answer in cards:
        cur.execute("""
            INSERT INTO flashcard (question, answer)
            VALUES (%s, %s)
            RETURNING cardID
        """, (question, answer))
        new_card_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO contains (cardID, setID)
            VALUES (%s, %s)
        """, (new_card_id, new_set_id))
    

    conn.commit()
    conn.close()

    return new_set_id

def delete_flashcard_set(set_id, user_id):
    conn = connect_db()
    cur = conn.cursor()

    
    cur.execute("SELECT setID FROM flashcardset WHERE setID = %s AND userID = %s", (set_id, user_id))
    if not cur.fetchone():
        conn.close()
        return False  
    
    cur.execute("DELETE FROM contains WHERE setID = %s", (set_id,))

    
    cur.execute("""
        DELETE FROM flashcard
        WHERE cardID IN (
            SELECT f.cardID
            FROM flashcard f
            LEFT JOIN contains c ON f.cardID = c.cardID
            WHERE c.setID IS NULL
        )
    """)

    
    cur.execute("DELETE FROM progress WHERE setID = %s AND userID = %s", (set_id, user_id))

    
    cur.execute("DELETE FROM flashcardset WHERE setID = %s", (set_id,))

    conn.commit()
    conn.close()
    return True

def get_recommended_sets_by_subject_and_likes(user_id, limit=5):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT f.setID, f.title, s.name AS subject, u.username,
            (
                SELECT COUNT(*) FROM likes l WHERE l.setID = f.setID
            ) AS like_count
        FROM flashcardset f
        JOIN subject s ON f.subjectID = s.subjectID
        JOIN users u ON f.userID = u.userID
        WHERE f.published = TRUE
          AND f.userID != %s
          AND f.subjectID IN (
              SELECT DISTINCT subjectID FROM flashcardset
              WHERE userID = %s
          )
        ORDER BY like_count DESC
        LIMIT %s;
    """, (user_id, user_id, limit))

    sets = cur.fetchall()
    conn.close()
    return sets

def like_flashcard_set(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO likes (userID, setID)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (user_id, set_id))
        conn.commit()
    finally:
        conn.close()

def unlike_flashcard_set(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM likes WHERE userID = %s AND setID = %s", (user_id, set_id))
    conn.commit()
    conn.close()

def has_liked_set(user_id, set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM likes WHERE userID = %s AND setID = %s", (user_id, set_id))
    result = cur.fetchone()
    conn.close()
    return bool(result)

def get_set_likes(set_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM likes WHERE setID = %s", (set_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def search_published_sets(query):
    conn = connect_db()
    cur = conn.cursor()

    like_query = f"%{query.lower()}%"
    cur.execute("""
        SELECT f.setID, f.title, s.name AS subject, u.username
        FROM flashcardset f
        JOIN subject s ON f.subjectID = s.subjectID
        JOIN users u ON f.userID = u.userID
        WHERE f.published = TRUE
          AND (
              LOWER(f.title) LIKE %s
              OR LOWER(s.name) LIKE %s
          )
    """, (like_query, like_query))

    results = cur.fetchall()
    conn.close()
    return results

def main():
    st.title("📚 QuickFlash")

    if "viewing_set_id" in st.session_state:
        show_flashcard_viewer()
        return
    if "review_set_id" in st.session_state:
        show_review_flashcards()
        return

    menu = ["Home", "Login", "SignUp", "My Sets", "Review Cards"]
    choice = st.sidebar.selectbox("Menu", menu)

    if 'user_id' in st.session_state:
        username, email = get_user_info(st.session_state['user_id'])
        st.sidebar.markdown(f"👤 **Logged in as:** {username} ({email})")
    
    if st.sidebar.button("🚪 Log Out"):
        st.session_state.clear()
        st.rerun()

    if choice == "Login":
        st.subheader("Login")
        show_login()
    elif choice == "SignUp":
        st.subheader("Create New Account")
        show_signup()
        
    elif choice == "My Sets":
        if "user_id" not in st.session_state:
            st.warning("Please log in to access your flashcard sets.")
        else:
            st.subheader("Your Flashcard Sets")
            with st.expander("➕ Create New Set"):
                title = st.text_input("Set Title")
            
            
                conn = connect_db()
                cur = conn.cursor()
                cur.execute("SELECT subjectID, name FROM subject")
                subjects = cur.fetchall()
                conn.close()

                subject_names = {name: sid for sid, name in subjects}
                subject_choice = st.selectbox("Subject", list(subject_names.keys()))

                if st.button("Create Set"):
                    if title and subject_choice:
                        new_set_id = create_flashcard_set(
                            st.session_state['user_id'],
                            title,
                            subject_names[subject_choice]
                        )   
                        st.success(f"Set '{title}' created! (ID: {new_set_id})")
                        st.rerun()  
            st.markdown("### 📁 Your Sets")
            sets = get_user_flashcard_sets(st.session_state['user_id'])
            if sets:
                for set_id, title, subject_name in sets:
                    col1, col2, col3 = st.columns([2, 1, 2])  

                    with col1:
                        if st.button(f"📂 Open '{title}'", key=f"open_{set_id}"):
                            st.session_state['active_set'] = {'id': set_id, 'title': title}
                            for key in list(st.session_state.keys()):
                                if key.startswith("new_card_q") or key.startswith("new_card_a"):
                                    del st.session_state[key]
                            st.rerun()

                    with col2:
                        if st.button(f"🗑️ Delete", key=f"del_set_{set_id}"):
                            if delete_flashcard_set(set_id, st.session_state["user_id"]):
                                st.success(f"Set '{title}' deleted.")
                                st.rerun()
                            else:
                                st.error("Failed to delete the set or unauthorized.")

                    with col3:
                        is_published = check_if_set_is_published(set_id)
                        if is_published:
                            if st.button(f"📤 Unpublish '{title}'", key=f"unpub_{set_id}"):
                                set_flashcardset_published(set_id, False)
                                st.success(f"Set '{title}' is now private.")
                                st.rerun()
                        else:
                            if st.button(f"🌍 Publish '{title}'", key=f"pub_{set_id}"):
                                set_flashcardset_published(set_id, True)
                                st.success(f"Set '{title}' is now public!")
                                st.rerun()
                if 'active_set' in st.session_state:
                    set_info = st.session_state['active_set']
                    st.markdown(f"## ✏️ Editing Set: **{set_info['title']}**")

                    set_id = set_info['id']

                    with st.expander("➕ Add New Flashcard"):
                        q_key = f"new_card_q_{set_id}"
                        a_key = f"new_card_a_{set_id}"

                        if q_key not in st.session_state:
                                st.session_state[q_key] = ""
                        if a_key not in st.session_state:
                                st.session_state[a_key] = ""

                        q = st.text_area("Question", value=st.session_state[q_key], key=q_key)
                        a = st.text_area("Answer", value=st.session_state[a_key], key=a_key)

                        if st.button("Add Card", key=f"add_card_btn_{set_id}"):
                            if q and a:
                                add_flashcard_to_set(set_id, q, a)
                                del st.session_state[q_key]
                                del st.session_state[a_key]
                                st.success("Flashcard added!")
                                st.rerun()
                            else:
                                st.warning("Please fill in both fields.")

                    flashcards = get_flashcards_in_set(set_id)
                    if flashcards:
                        for card_id, question, answer in flashcards:
                            with st.expander(f"🃏 {question[:30]}..."):
                                new_q = st.text_area("Edit Question", value=question, key=f"q{card_id}")
                                new_a = st.text_area("Edit Answer", value=answer, key=f"a{card_id}")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("💾 Save", key=f"save{card_id}"):
                                        update_flashcard(card_id, new_q, new_a)
                                        st.success("Flashcard updated!")
                                        st.rerun()
                                with col2:
                                    if st.button("🗑️ Delete", key=f"del{card_id}"):
                                        delete_flashcard(card_id)
                                        st.warning("Flashcard deleted.")
                                        st.rerun()
                    else:
                        st.info("No flashcards in this set yet.")

                        
            else:
                st.info("No sets yet. Create one above!")
    elif choice == "Review Cards":
        if "user_id" not in st.session_state:
            st.warning("Please log in to review flashcards.")
        else:
            st.subheader("🔁 Review Your Flashcards")

            
            sets = get_user_flashcard_sets(st.session_state["user_id"])
            set_titles = {f"{title} ({subject})": set_id for set_id, title, subject in sets}
            set_choice = st.selectbox("Choose a set", list(set_titles.keys()))

            if st.button("Start Review"):
                st.session_state["review_set_id"] = set_titles[set_choice]
                st.session_state["review_index"] = 0
                st.session_state["review_show_answer"] = False
                st.rerun()

# Review Session(NO LONGER USED)
    if 'review_cards' in st.session_state and st.session_state['review_cards']:
        index = st.session_state['review_index']
        cards = st.session_state['review_cards']

        if index < len(cards):
            card_id, question, answer = cards[index]
            st.markdown(f"**Card {index + 1} of {len(cards)}**")
            st.markdown(f"### ❓ {question}")

            if not st.session_state.get('show_answer', False):
                if st.button("👁️ Show Answer"):
                    st.session_state['show_answer'] = True
            else:
                st.markdown(f"### ✅ {answer}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Got it ✅"):
                        st.session_state['review_index'] += 1
                        st.session_state['show_answer'] = False
                with col2:
                    if st.button("Need to Review 🔁"):
                    
                        cards.append((card_id, question, answer))
                        st.session_state['review_index'] += 1
                        st.session_state['show_answer'] = False
        else:
            st.success("🎉 Review complete!")
            if st.button("🔄 Start Over"):
                del st.session_state['review_cards']
                del st.session_state['review_index']
                del st.session_state['show_answer']
                del st.session_state['review_set_id']
                st.rerun()
    elif choice == "Home":
        st.title("🏠 Home - Explore Flashcard Sets")

        user_id = st.session_state.get('user_id')

        st.subheader("🔎 Search Published Sets")
        search_query = st.text_input("Search by title or subject")

        if search_query:
            sets = search_published_sets(search_query)
            if not sets:
                st.info("No sets matched your search.")
            else:
                st.markdown("### 🔍 Search Results")
                for set_id, title, subject, creator in sets:
                    st.markdown(f"**📚 {title}**")
                    st.markdown(f"Subject: {subject} | By: {creator}")
                    if st.button(f"🔍 View Set: {title}", key=f"search_view_{set_id}"):
                        st.session_state["viewing_set_id"] = set_id
                        st.session_state["current_card"] = 0
                        st.session_state["show_answer"] = False
                        st.rerun()

        
        elif user_id:
            recommended_sets = get_recommended_sets_by_subject_and_likes(user_id)
            if recommended_sets:
                st.subheader("✨ Recommended for You")
                for set_id, title, subject, creator, like_count in recommended_sets:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**📘 {title}** — {subject} by *{creator}*")
                        st.markdown(f"❤️ {like_count} likes")
                    with col2:
                        if st.button("🔍 View", key=f"reco_view_{set_id}"):
                            st.session_state["viewing_set_id"] = set_id
                            st.session_state["current_card"] = 0
                            st.session_state["show_answer"] = False
                            st.rerun()
                    with col3:
                        if st.button("📄 Copy", key=f"reco_copy_{set_id}"):
                            new_id = copy_flashcard_set(set_id, user_id)
                            st.success(f"Copied to My Sets (ID: {new_id})")
                            st.rerun()

        st.markdown("---")
        st.subheader("🌍 All Published Sets")

        all_sets = get_published_flashcard_sets()
        for set_id, title, subject, creator in all_sets:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**📘 {title}** — {subject} by *{creator}*")
                if user_id:
                    like_count = get_set_likes(set_id)
                    liked = has_liked_set(user_id, set_id)
                    if liked:
                        if st.button("💔 Unlike", key=f"unlike_{set_id}"):
                            unlike_flashcard_set(user_id, set_id)
                            st.rerun()
                    else:
                        if st.button("❤️ Like", key=f"like_{set_id}"):
                            like_flashcard_set(user_id, set_id)
                            st.rerun()
                    st.markdown(f"👍 {like_count} likes")

            with col2:
                if st.button("🔍 View", key=f"view_{set_id}"):
                    st.session_state["viewing_set_id"] = set_id
                    st.session_state["current_card"] = 0
                    st.session_state["show_answer"] = False
                    st.rerun()

            with col3:
                if user_id:
                    if st.button("📄 Copy", key=f"copy_{set_id}"):
                        new_id = copy_flashcard_set(set_id, user_id)
                        st.success(f"Copied to My Sets (ID: {new_id})")
                        st.rerun()


if __name__ == "__main__":
    main()