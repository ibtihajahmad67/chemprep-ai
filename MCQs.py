import streamlit as st
import google.generativeai as genai
from supabase import create_client
import json, time, re, random, string, hashlib
from datetime import datetime

GEMINI_KEY     = st.secrets.get("GEMINI_KEY","")
SUPABASE_URL   = st.secrets.get("SUPABASE_URL","")
SUPABASE_KEY   = st.secrets.get("SUPABASE_KEY","")
TEACHER_SECRET = st.secrets.get("TEACHER_SECRET","ibtihaj2024")

genai.configure(api_key=GEMINI_KEY)
ai  = genai.GenerativeModel("gemini-2.5-flash-lite")
sb  = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="ChemPrep AI", page_icon="⚗️", layout="centered")
st.markdown("""<style>
.big{text-align:center;font-size:2.4em;font-weight:bold;color:#4A90D9;}
.sub{text-align:center;color:#888;margin-bottom:15px;}
.card{background:#f8f9fa;border-radius:12px;padding:18px;margin:8px 0;border-left:4px solid #4A90D9;}
.stButton>button{border-radius:10px;font-weight:bold;}
</style>""",unsafe_allow_html=True)

def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

def safe_json(text):
    text=re.sub(r'```json\s*','',text); text=re.sub(r'```\s*','',text).strip()
    try: return json.loads(text)
    except: pass
    m=re.search(r'\[.*\]',text,re.DOTALL)
    if m:
        try: return json.loads(m.group())
        except: pass
    m=re.search(r'\{.*\}',text,re.DOTALL)
    if m:
        try: return json.loads(m.group())
        except: pass
    raise ValueError("JSON parse failed")

def gen_code(): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=8))

def q_timer(limit):
    if st.session_state.q_t is None:
        st.session_state.q_t=time.time(); st.session_state.time_up=False
    rem=max(0,limit-int(time.time()-st.session_state.q_t))
    m,s=rem//60,rem%60
    c="green" if rem>limit*0.4 else("orange" if rem>10 else"red")
    st.markdown(f"<p style='color:{c};font-weight:bold;font-size:15px;'>⏱️ Q: {m:02d}:{s:02d}</p>",unsafe_allow_html=True)
    if rem==0: st.session_state.time_up=True
    return rem

def total_timer():
    if not st.session_state.get("t_start"): return
    rem=max(0,st.session_state.t_limit-int(time.time()-st.session_state.t_start))
    m,s=rem//60,rem%60
    c="green" if rem>st.session_state.t_limit*0.4 else("orange" if rem>60 else"red")
    st.markdown(f"<p style='color:{c};font-weight:bold;font-size:15px;'>🕐 Total: {m:02d}:{s:02d}</p>",unsafe_allow_html=True)
    if rem==0: st.session_state.quiz_done=True; st.rerun()

defs={"page":"home","user":None,"role":None,"quiz_started":False,"quiz_done":False,
      "all_questions":[],"current_q":0,"answers":{},"submitted_current":False,
      "score":0,"total_marks":0,"saq_eval":{},"q_t":None,"t_start":None,"t_limit":0,
      "time_up":False,"streak":0,"max_streak":0,"hint_used":{},"bookmarked":[],
      "test_mode":None,"attempt_id":None,"test_id":None,
      "skipped_questions":[],"question_order":[],"showing_result":False}
for k,v in defs.items():
    if k not in st.session_state: st.session_state[k]=v

# HOME
if st.session_state.page=="home":
    st.markdown("<div class='big'>⚗️ ChemPrep AI</div>",unsafe_allow_html=True)
    st.markdown("<div class='sub'>AI-Powered Chemistry for FSc (11th & 12th) and MDCAT</div>",unsafe_allow_html=True)
    st.markdown("---")
    if st.button("📚 Student Login / Register",use_container_width=True):
        st.session_state.page="student_auth"; st.rerun()
    st.markdown("<br>",unsafe_allow_html=True)
    with st.expander("🔐 Teacher Access"):
        sec=st.text_input("Access code:",type="password",key="tsec")
        if st.button("Verify",key="vsec"):
            if sec==TEACHER_SECRET: st.session_state.page="teacher_auth"; st.rerun()
            else: st.error("❌ Wrong code!")

# TEACHER AUTH
elif st.session_state.page=="teacher_auth":
    st.title("👨‍🏫 Teacher Login")
    tab1,tab2,tab3=st.tabs(["Login","Register","🔑 Reset Password"])
    with tab1:
        e=st.text_input("Email:",key="tle"); p=st.text_input("Password:",type="password",key="tlp")
        if st.button("Login",use_container_width=True,key="tlb"):
            r=sb.table("users").select("*").eq("email",e).eq("role","teacher").execute()
            if r.data and r.data[0]["password_hash"]==hp(p):
                st.session_state.user=r.data[0]; st.session_state.role="teacher"
                st.session_state.page="teacher_dashboard"; st.rerun()
            else: st.error("❌ Wrong credentials! Forgot password? Use Reset Password tab.")
    with tab2:
        n=st.text_input("Name:",key="trn"); e2=st.text_input("Email:",key="tre"); p2=st.text_input("Password:",type="password",key="trp")
        if st.button("Register",use_container_width=True,key="trb"):
            try: sb.table("users").insert({"name":n,"email":e2,"role":"teacher","password_hash":hp(p2)}).execute(); st.success("✅ Done! Login now.")
            except: st.error("❌ Email exists!")
    with tab3:
        st.info("Enter your email + Teacher Secret Code + new password to reset.")
        re_email=st.text_input("Registered email:",key="tre2")
        re_secret=st.text_input("Teacher secret code:",type="password",key="tres")
        re_newp=st.text_input("New password:",type="password",key="trnp")
        re_newp2=st.text_input("Confirm new password:",type="password",key="trnp2")
        if st.button("🔄 Reset Password",use_container_width=True,key="treset"):
            if re_secret!=TEACHER_SECRET: st.error("❌ Wrong secret code!")
            elif re_newp!=re_newp2: st.error("❌ Passwords do not match!")
            elif len(re_newp)<4: st.error("❌ Password too short!")
            else:
                r=sb.table("users").select("*").eq("email",re_email).eq("role","teacher").execute()
                if not r.data: st.error("❌ No teacher account found with this email!")
                else:
                    sb.table("users").update({"password_hash":hp(re_newp)}).eq("email",re_email).eq("role","teacher").execute()
                    st.success("✅ Password reset! Go to Login tab and login with new password.")
    if st.button("← Back"): st.session_state.page="home"; st.rerun()

# STUDENT AUTH
elif st.session_state.page=="student_auth":
    st.title("👨‍🎓 Student Login")
    tab1,tab2,tab3=st.tabs(["Login","Register","🔑 Forgot Password"])
    with tab1:
        e=st.text_input("Email:",key="sle"); p=st.text_input("Password:",type="password",key="slp")
        if st.button("Login",use_container_width=True,key="slb"):
            r=sb.table("users").select("*").eq("email",e).eq("role","student").execute()
            if r.data and r.data[0]["password_hash"]==hp(p):
                st.session_state.user=r.data[0]; st.session_state.role="student"
                st.session_state.page="student_home"; st.rerun()
            else: st.error("❌ Wrong email or password!")
    with tab2:
        n=st.text_input("Name:",key="srn"); e2=st.text_input("Email:",key="sre"); p2=st.text_input("Password:",type="password",key="srp")
        if st.button("Register",use_container_width=True,key="srb"):
            if not n.strip(): st.error("❌ Please enter your name!")
            elif not e2.strip() or "@" not in e2: st.error("❌ Please enter a valid email!")
            elif len(p2)<4: st.error("❌ Password must be at least 4 characters!")
            else:
                try:
                    sb.table("users").insert({"name":n,"email":e2,"role":"student","password_hash":hp(p2)}).execute()
                    st.success("✅ Account created! Go to Login tab and login now.")
                except: st.error("❌ This email is already registered! Try logging in.")
    with tab3:
        st.info("Enter your registered email and a new password to reset.")
        fp_email=st.text_input("Registered email:",key="sfpe")
        fp_newp=st.text_input("New password:",type="password",key="sfpnp")
        fp_newp2=st.text_input("Confirm new password:",type="password",key="sfpnp2")
        if st.button("🔄 Reset Password",use_container_width=True,key="sfpreset"):
            if not fp_email.strip() or "@" not in fp_email: st.error("❌ Please enter a valid email!")
            elif fp_newp!=fp_newp2: st.error("❌ Passwords do not match!")
            elif len(fp_newp)<4: st.error("❌ Password too short! Minimum 4 characters.")
            else:
                r=sb.table("users").select("*").eq("email",fp_email).eq("role","student").execute()
                if not r.data: st.error("❌ No student account found with this email!")
                else:
                    sb.table("users").update({"password_hash":hp(fp_newp)}).eq("email",fp_email).eq("role","student").execute()
                    st.success("✅ Password reset successfully! Go to Login tab and login with your new password.")
    if st.button("← Back"): st.session_state.page="home"; st.rerun()

# TEACHER DASHBOARD
elif st.session_state.page=="teacher_dashboard":
    u=st.session_state.user
    st.title(f"👨‍🏫 {u['name']}")
    tab1,tab2,tab3,tab4=st.tabs(["➕ Create Test","📖 Question Bank","📋 My Tests","📊 All Results"])

    with tab1:
        st.markdown("### Create New Test")
        title=st.text_input("Test Title:")
        q_source=st.radio("Question source:",["🤖 AI — Auto generate","✍️ Manual — I will write","📖 Bank — From my saved questions"],key="qsrc")
        restrict_topic=st.toggle("🔒 Restrict topic (optional)",value=False)
        topic=""
        if restrict_topic or "AI" in q_source:
            topic=st.text_input("Topic:",placeholder="e.g. Chemical Bonding")
        c1,c2=st.columns(2)
        with c1: use_mcq=st.checkbox("MCQs",value=True,key="ctm")
        with c2: use_saq=st.checkbox("SAQs",key="cts")
        mcq_count=mcq_marks=saq_count=saq_marks=0
        if use_mcq:
            x1,x2=st.columns(2)
            with x1: mcq_count=st.number_input("No. MCQs:",1,30,5,1,key="ctmn")
            with x2: mcq_marks=st.number_input("Marks/MCQ:",1,10,1,1,key="ctmm")
        if use_saq:
            x1,x2=st.columns(2)
            with x1: saq_count=st.number_input("No. SAQs:",1,20,3,1,key="ctsn")
            with x2: saq_marks=st.number_input("Marks/SAQ:",1,10,2,1,key="ctsm")
        manual_questions=[]
        if "Manual" in q_source:
            st.markdown("#### ✍️ Write Questions")
            nm=st.number_input("How many?",1,20,3,1,key="nm")
            for i in range(int(nm)):
                st.markdown(f"**Q{i+1}:**")
                qt=st.selectbox("Type:",["MCQ","SAQ"],key=f"mqt{i}")
                qtxt=st.text_area("Question:",key=f"mqtxt{i}",height=70)
                qmrk=st.number_input("Marks:",1,10,1,key=f"mqmrk{i}")
                if qt=="MCQ":
                    a=st.text_input("A:",key=f"mqa{i}"); b=st.text_input("B:",key=f"mqb{i}")
                    c=st.text_input("C:",key=f"mqc{i}"); d=st.text_input("D:",key=f"mqd{i}")
                    ans=st.selectbox("Correct:",["A","B","C","D"],key=f"mqans{i}")
                    exp=st.text_area("Explanation:",key=f"mqexp{i}",height=50)
                    manual_questions.append({"question":qtxt,"type":"mcq","marks":qmrk,"options":[f"A) {a}",f"B) {b}",f"C) {c}",f"D) {d}"],"answer":ans,"explanation":exp,"hint":""})
                else:
                    mans=st.text_area("Model Answer:",key=f"mqmans{i}",height=70)
                    manual_questions.append({"question":qtxt,"type":"saq","marks":qmrk,"model_answer":mans,"answer":mans,"hint":""})
                st.markdown("---")
        bank_selected=[]
        if "Bank" in q_source:
            st.markdown("#### 📖 Select from Bank")
            bank=sb.table("question_bank").select("*").eq("teacher_id",u["id"]).execute()
            if not bank.data: st.info("Bank is empty.")
            for bq in (bank.data or []):
                if st.checkbox(f"[{bq['question_type'].upper()}] {bq['question_text'][:80]}",key=f"bqs{bq['id']}"):
                    bank_selected.append(bq)
        mt=sum(180 if q["type"]=="saq" else 60 for q in manual_questions+bank_selected)
        at=(int(mcq_count)*60 if use_mcq and "AI" in q_source else 0)+(int(saq_count)*180 if use_saq and "AI" in q_source else 0)
        tmin=(at+mt)//60+5
        st.info(f"🕐 Test time: **{tmin} min**")
        if st.button("🚀 Generate Test & Get Code",use_container_width=True):
            if not title: st.warning("⚠️ Enter title!")
            else:
                with st.spinner("⏳ Creating..."):
                    all_q=[]
                    if "AI" in q_source and topic:
                        if use_mcq and mcq_count>0:
                            r=ai.generate_content(f"Create {int(mcq_count)} MCQs on {topic} for FSc/MDCAT. ONLY JSON ARRAY:\n[{{\"question\":\"?\",\"options\":[\"A) a\",\"B) b\",\"C) c\",\"D) d\"],\"answer\":\"A\",\"explanation\":\"...\",\"hint\":\"...\"}}]")
                            for i,q in enumerate(safe_json(r.text)): q.update({"type":"mcq","marks":int(mcq_marks),"order_num":len(all_q)+i+1}); all_q.append(q)
                        if use_saq and saq_count>0:
                            r=ai.generate_content(f"Create {int(saq_count)} SAQs on {topic} for FSc/MDCAT. ONLY JSON ARRAY:\n[{{\"question\":\"?\",\"model_answer\":\"2-3 sentences.\",\"hint\":\"...\"}}]")
                            for i,q in enumerate(safe_json(r.text)): q.update({"type":"saq","marks":int(saq_marks),"order_num":len(all_q)+i+1}); all_q.append(q)
                    for i,q in enumerate(manual_questions): q["order_num"]=len(all_q)+i+1; all_q.append(q)
                    for i,bq in enumerate(bank_selected):
                        all_q.append({"question":bq["question_text"],"type":bq["question_type"],"options":bq.get("options"),"answer":bq.get("correct_answer"),"model_answer":bq.get("correct_answer"),"explanation":bq.get("explanation",""),"hint":bq.get("hint",""),"marks":bq.get("marks",1),"order_num":len(all_q)+i+1})
                    if not all_q: st.warning("⚠️ No questions added!"); st.stop()
                    code=gen_code()
                    tr=sb.table("tests").insert({"teacher_id":u["id"],"title":title,"topic":topic,"test_code":code,"time_limit_minutes":tmin,"is_active":True}).execute()
                    tid=tr.data[0]["id"]
                    for q in all_q:
                        sb.table("questions").insert({"test_id":tid,"question_text":q["question"],"question_type":q["type"],"options":q.get("options"),"correct_answer":q.get("answer") or q.get("model_answer",""),"explanation":q.get("explanation",""),"hint":q.get("hint",""),"marks":q.get("marks",1),"order_num":q.get("order_num",1)}).execute()
                    st.success("✅ Test created!")
                    st.markdown(f"## 🔑 Code: `{code}`")
                    st.info("Share this code with students!")

    with tab2:
        st.markdown("### 📖 Question Bank")
        with st.expander("➕ Add Question"):
            bqt=st.selectbox("Type:",["MCQ","SAQ"],key="bqt")
            bqtxt=st.text_area("Question:",key="bqtxt",height=70)
            btopic=st.text_input("Topic:",key="bqtopic")
            bmarks=st.number_input("Marks:",1,10,1,key="bqmarks")
            if bqt=="MCQ":
                ba=st.text_input("A:",key="bqa"); bb=st.text_input("B:",key="bqb")
                bc=st.text_input("C:",key="bqc"); bd=st.text_input("D:",key="bqd")
                bans=st.selectbox("Correct:",["A","B","C","D"],key="bqans")
                bexp=st.text_area("Explanation:",key="bqexp",height=50)
                if st.button("💾 Save",key="sbq"):
                    if bqtxt: sb.table("question_bank").insert({"teacher_id":u["id"],"question_text":bqtxt,"question_type":"mcq","topic":btopic,"marks":bmarks,"options":[f"A) {ba}",f"B) {bb}",f"C) {bc}",f"D) {bd}"],"correct_answer":bans,"explanation":bexp}).execute(); st.success("✅ Saved!"); st.rerun()
            else:
                bmans=st.text_area("Model Answer:",key="bqmans",height=70)
                if st.button("💾 Save",key="sbqsaq"):
                    if bqtxt: sb.table("question_bank").insert({"teacher_id":u["id"],"question_text":bqtxt,"question_type":"saq","topic":btopic,"marks":bmarks,"correct_answer":bmans}).execute(); st.success("✅ Saved!"); st.rerun()
        bank=sb.table("question_bank").select("*").eq("teacher_id",u["id"]).execute()
        if not (bank.data): st.info("Empty.")
        for bq in (bank.data or []):
            with st.expander(f"[{bq['question_type'].upper()}] {bq['question_text'][:70]}"):
                st.write(f"Topic: {bq.get('topic','')} | Marks: {bq.get('marks',1)}")
                if bq["question_type"]=="mcq":
                    for o in (bq.get("options") or []): st.write(o)
                    st.write(f"Answer: {bq.get('correct_answer','')}")
                else: st.write(f"Answer: {bq.get('correct_answer','')}")
                if st.button("🗑️ Delete",key=f"delbq{bq['id']}"): sb.table("question_bank").delete().eq("id",bq["id"]).execute(); st.rerun()

    with tab3:
        st.markdown("### My Tests")
        tests=sb.table("tests").select("*").eq("teacher_id",u["id"]).execute()
        if not tests.data: st.info("No tests yet.")
        for t in (tests.data or []):
            with st.expander(f"📋 {t['title']} — `{t['test_code']}`"):
                st.write(f"Topic: {t.get('topic','')} | Time: {t['time_limit_minutes']} min | {'🟢 Active' if t['is_active'] else '🔴 Inactive'}")
                c1,c2=st.columns(2)
                with c1:
                    if st.button("🟢 Activate" if not t["is_active"] else "🔴 Deactivate",key=f"tog{t['id']}"): sb.table("tests").update({"is_active":not t["is_active"]}).eq("id",t["id"]).execute(); st.rerun()
                with c2:
                    if st.button("🗑️ Delete",key=f"delt{t['id']}"):
                        sb.table("questions").delete().eq("test_id",t["id"]).execute()
                        sb.table("tests").delete().eq("id",t["id"]).execute(); st.rerun()

    with tab4:
        st.markdown("### 📊 All Results")
        tests=sb.table("tests").select("*").eq("teacher_id",u["id"]).execute()
        tmap={t["id"]:t["title"] for t in (tests.data or [])}
        tids=[t["id"] for t in (tests.data or [])]
        ft=st.selectbox("Filter:",["All"]+[t["title"] for t in (tests.data or [])],key="rf")
        all_atts=[]
        for tid in tids:
            if ft=="All" or tmap.get(tid)==ft:
                att=sb.table("attempts").select("*").eq("test_id",tid).eq("completed",True).execute()
                all_atts.extend(att.data)
        if not all_atts: st.info("No results.")
        for att in all_atts:
            stu=sb.table("users").select("name,email").eq("id",att["student_id"]).execute()
            sn=stu.data[0]["name"] if stu.data else "?"
            se=stu.data[0]["email"] if stu.data else ""
            pct=att.get("percentage",0)
            ic="🌟" if pct>=80 else("👍" if pct>=60 else("📚" if pct>=40 else"💪"))
            st.markdown(f"{ic} **{sn}** ({se}) — {tmap.get(att['test_id'],'?')} — **{att['score']}/{att['total_marks']}** ({pct:.1f}%)")

    if st.button("🚪 Logout",key="tout"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# STUDENT HOME
elif st.session_state.page=="student_home":
    u=st.session_state.user
    st.title(f"👨‍🎓 {u['name']}")
    tab1,tab2,tab3=st.tabs(["📝 Teacher's Test","🤖 AI Practice","📊 My Progress"])

    with tab1:
        st.markdown("### Enter Test Code")
        code=st.text_input("Code:",placeholder="e.g. ABC12345").strip().upper()
        if st.button("🚀 Start Test",use_container_width=True,key="sstart"):
            if not code: st.warning("⚠️ Enter code!")
            else:
                res=sb.table("tests").select("*").eq("test_code",code).execute()
                if not res.data: st.error("❌ Invalid code!")
                elif not res.data[0]["is_active"]: st.error("❌ Test not active.")
                else:
                    test=res.data[0]
                    qs=sb.table("questions").select("*").eq("test_id",test["id"]).order("order_num").execute()
                    questions=[{"question":q["question_text"],"type":q["question_type"],"options":q.get("options"),"answer":q.get("correct_answer") if q["question_type"]=="mcq" else None,"model_answer":q.get("correct_answer") if q["question_type"]=="saq" else None,"explanation":q.get("explanation",""),"hint":q.get("hint",""),"marks":q["marks"],"db_id":q["id"]} for q in qs.data]
                    att=sb.table("attempts").insert({"student_id":u["id"],"test_id":test["id"],"total_marks":sum(q["marks"] for q in questions)}).execute()
                    st.session_state.update({"all_questions":questions,"test_id":test["id"],"attempt_id":att.data[0]["id"],"total_marks":sum(q["marks"] for q in questions),"t_start":time.time(),"t_limit":test["time_limit_minutes"]*60,"current_q":0,"answers":{},"submitted_current":False,"score":0,"saq_eval":{},"q_t":None,"time_up":False,"streak":0,"max_streak":0,"hint_used":{},"bookmarked":[],"quiz_started":True,"quiz_done":False,"test_mode":"teacher","page":"quiz","skipped_questions":[],"question_order":list(range(len(questions))),"showing_result":False})
                    st.rerun()

    with tab2:
        st.markdown("### 🤖 AI Practice — Your Choice!")
        topic=st.text_input("Choose any topic:",placeholder="e.g. Atomic Structure, Gases...")
        st.markdown("**Select question type(s):**")
        col_mcq,col_saq=st.columns(2)
        with col_mcq:
            um=st.checkbox("MCQs",value=False,key="apm")
            if um:
                mn=st.number_input("Number of MCQs:",1,30,5,1,key="apmn")
                mm=st.number_input("Marks per MCQ:",1,10,1,1,key="apmm")
            else:
                mn=mm=0
        with col_saq:
            us=st.checkbox("SAQs",value=False,key="aps")
            if us:
                sn=st.number_input("Number of SAQs:",1,20,3,1,key="apsn")
                sm=st.number_input("Marks per SAQ:",1,10,2,1,key="apsm")
            else:
                sn=sm=0
        if st.button("🤖 Start AI Practice",use_container_width=True):
            if not topic.strip(): st.error("❌ Please enter a topic first!")
            elif not um and not us: st.error("❌ Please select at least one question type — MCQs or SAQs!")
            else:
                with st.spinner("⏳ Generating..."):
                    all_q=[]
                    if um and mn>0:
                        r=ai.generate_content(f"Create {int(mn)} MCQs on {topic} for FSc/MDCAT. ONLY JSON:\n[{{\"question\":\"?\",\"options\":[\"A) a\",\"B) b\",\"C) c\",\"D) d\"],\"answer\":\"A\",\"explanation\":\"...\",\"hint\":\"...\"}}]")
                        for q in safe_json(r.text): q.update({"type":"mcq","marks":int(mm)}); all_q.append(q)
                    if us and sn>0:
                        r=ai.generate_content(f"Create {int(sn)} SAQs on {topic} for FSc/MDCAT. ONLY JSON:\n[{{\"question\":\"?\",\"model_answer\":\"2-3 sentences.\",\"hint\":\"...\"}}]")
                        for q in safe_json(r.text): q.update({"type":"saq","marks":int(sm),"answer":None}); all_q.append(q)
                    ts=(int(mn)*60 if um else 0)+(int(sn)*180 if us else 0)+300
                    st.session_state.update({"all_questions":all_q,"test_id":None,"attempt_id":None,"total_marks":sum(q["marks"] for q in all_q),"t_start":time.time(),"t_limit":ts,"current_q":0,"answers":{},"submitted_current":False,"score":0,"saq_eval":{},"q_t":None,"time_up":False,"streak":0,"max_streak":0,"hint_used":{},"bookmarked":[],"quiz_started":True,"quiz_done":False,"test_mode":"ai","page":"quiz","skipped_questions":[],"question_order":list(range(len(all_q))),"showing_result":False})
                    st.rerun()

    with tab3:
        st.markdown("### 📊 My Progress")
        atts=sb.table("attempts").select("*").eq("student_id",u["id"]).eq("completed",True).execute()
        if not atts.data: st.info("No tests yet.")
        else:
            ta=len(atts.data); ap=sum(a.get("percentage",0) for a in atts.data)/ta; best=max(atts.data,key=lambda x:x.get("percentage",0))
            c1,c2,c3=st.columns(3)
            with c1: st.metric("Tests Taken",ta)
            with c2: st.metric("Average %",f"{ap:.1f}%")
            with c3: st.metric("Best %",f"{best.get('percentage',0):.1f}%")
            st.markdown("---")
            months=sorted(set(a["started_at"][:7] for a in atts.data),reverse=True)
            sm=st.selectbox("Filter by month:",["All Time"]+months,key="mf")
            filtered=[a for a in atts.data if sm=="All Time" or a["started_at"][:7]==sm]
            for att in reversed(filtered):
                if att.get("test_id"):
                    t=sb.table("tests").select("title").eq("id",att["test_id"]).execute()
                    tn=t.data[0]["title"] if t.data else "Test"
                else: tn="AI Practice"
                pct=att.get("percentage",0); d=att["started_at"][:10]
                ic="🌟" if pct>=80 else("👍" if pct>=60 else("📚" if pct>=40 else"💪"))
                st.markdown(f"{ic} **{tn}** — {att['score']}/{att['total_marks']} ({pct:.1f}%) — *{d}*")
            if len(filtered)>=2:
                st.markdown("#### 📈 Trend")
                import pandas as pd
                df=pd.DataFrame([{"Test":f"T{i+1}","Percentage":a.get("percentage",0)} for i,a in enumerate(filtered)])
                st.line_chart(df.set_index("Test"))

    if st.button("🚪 Logout",key="sout"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# QUIZ
elif st.session_state.page=="quiz" and not st.session_state.quiz_done:
    questions=st.session_state.all_questions
    # Build question_order if not set (safety)
    if not st.session_state.question_order:
        st.session_state.question_order=list(range(len(questions)))
    order=st.session_state.question_order
    skipped=st.session_state.skipped_questions

    # current_q is a position in order list
    pos=st.session_state.current_q
    # If we've exhausted the main order, move to skipped
    if pos>=len(order):
        # All regular questions done — now do skipped ones in order
        if skipped:
            st.session_state.question_order=skipped[:]
            st.session_state.skipped_questions=[]
            st.session_state.current_q=0
            st.session_state.submitted_current=False
            st.session_state.showing_result=False
            st.session_state.q_t=None
            st.session_state.time_up=False
            st.rerun()
        else:
            st.session_state.quiz_done=True
            if st.session_state.attempt_id:
                pct=(st.session_state.score/st.session_state.total_marks*100) if st.session_state.total_marks>0 else 0
                sb.table("attempts").update({"score":st.session_state.score,"percentage":pct,"completed":True,"completed_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}).eq("id",st.session_state.attempt_id).execute()
            st.rerun()
        st.stop()

    idx=order[pos]
    q=questions[idx]; total=len(order)+len(skipped); tlimit=60 if q["type"]=="mcq" else 180

    st.title("⚗️ ChemPrep AI")
    c1,c2,c3=st.columns(3)
    with c1: s=st.session_state.streak; st.markdown(f"**{'🔥' if s>=3 else '✨' if s>=1 else ''} Streak: {s}**")
    with c2:
        if not st.session_state.submitted_current: q_timer(tlimit)
        else: st.markdown("✅ Submitted")
    with c3: total_timer()

    # Progress bar shows position across all (order + skipped remaining)
    done_count=pos
    st.markdown(f"**Q{pos+1}/{len(order)}** | **{'MCQ' if q['type']=='mcq' else 'SAQ'}** | **{q['marks']} mark(s)**")
    if skipped: st.caption(f"⏭️ {len(skipped)} skipped question(s) will appear at the end")
    st.progress(pos/max(len(order),1)); st.markdown("---")

    # Time up auto-submit
    if st.session_state.time_up and not st.session_state.submitted_current:
        st.warning("⏰ Time's up!")
        st.session_state.answers[idx]="X" if q["type"]=="mcq" else "(Time expired)"
        st.session_state.submitted_current=True; st.session_state.showing_result=True
        st.session_state.streak=0; st.rerun()

    # Question card
    st.markdown(f"<div class='card'><b>Q{pos+1}:</b> {q['question']}</div>",unsafe_allow_html=True)

    # Bookmark
    is_bm=idx in st.session_state.bookmarked
    if st.button("🔖 Bookmarked" if is_bm else "📌 Bookmark",key=f"bm{idx}"):
        if is_bm: st.session_state.bookmarked.remove(idx)
        else: st.session_state.bookmarked.append(idx)
        st.rerun()

    # Hint
    hint_val=str(q.get("hint","")).strip()
    if not st.session_state.submitted_current and hint_val and hint_val.lower()!="none":
        if idx not in st.session_state.hint_used:
            if st.button("💡 Hint",key=f"h{idx}"): st.session_state.hint_used[idx]=True; st.rerun()
        if idx in st.session_state.hint_used: st.warning(f"💡 {hint_val}")

    # ── MCQ ──────────────────────────────────────────────────────────────
    if q["type"]=="mcq":
        if not st.session_state.submitted_current:
            choice=st.radio("Choose:",q["options"],key=f"r{idx}",index=None)
            btn_col1,btn_col2=st.columns([3,1])
            with btn_col1:
                if st.button("✅ Submit Answer",use_container_width=True,key=f"sub{idx}"):
                    if choice is None:
                        st.error("❌ Please select an option before submitting!")
                        st.stop()
                    st.session_state.answers[idx]=choice[0]; st.session_state.submitted_current=True
                    st.session_state.showing_result=True; st.session_state.q_t=None
                    correct=choice[0]==q["answer"]
                    if correct: st.session_state.score+=q["marks"]; st.session_state.streak+=1; st.session_state.max_streak=max(st.session_state.streak,st.session_state.max_streak)
                    else: st.session_state.streak=0
                    if st.session_state.attempt_id and q.get("db_id"): sb.table("answers").insert({"attempt_id":st.session_state.attempt_id,"question_id":q["db_id"],"given_answer":choice[0],"is_correct":correct,"marks_awarded":q["marks"] if correct else 0}).execute()
                    st.rerun()
            with btn_col2:
                if idx not in skipped:
                    if st.button("⏭️ Skip",use_container_width=True,key=f"skip{idx}"):
                        st.session_state.skipped_questions.append(idx)
                        # advance to next in order
                        st.session_state.current_q=pos+1
                        st.session_state.submitted_current=False
                        st.session_state.showing_result=False
                        st.session_state.q_t=None; st.session_state.time_up=False
                        st.session_state.hint_used={}
                        st.rerun()
        # Show result ONLY when showing_result is True
        elif st.session_state.showing_result and idx in st.session_state.answers:
            sel=st.session_state.answers[idx]
            for opt in q["options"]:
                if opt.startswith(sel) and opt.startswith(q["answer"]): st.markdown(f"🟢 **{opt}** ✅ Correct!")
                elif opt.startswith(sel): st.markdown(f"🔴 **{opt}** ❌ Your answer")
                elif opt.startswith(q["answer"]): st.markdown(f"🟢 **{opt}** ✅ Correct answer")
                else: st.markdown(f"⚪ {opt}")
            if sel==q["answer"]:
                st.success(f"✅ +{q['marks']} mark(s)")
                if st.session_state.streak>=3: st.balloons()
            else:
                co=next((o for o in q["options"] if o.startswith(q["answer"])),q["answer"]); st.error(f"❌ Correct: **{co}**")
            exp_val=str(q.get("explanation","")).strip()
            if exp_val and exp_val.lower()!="none":
                st.info(f"📖 **Explanation:** {exp_val}")
            else:
                st.info("📖 **Explanation:** Not available for this question.")

    # ── SAQ ──────────────────────────────────────────────────────────────
    elif q["type"]=="saq":
        if not st.session_state.submitted_current:
            ua=st.text_area("Your answer:",key=f"saq{idx}",height=120)
            btn_col1,btn_col2=st.columns([3,1])
            with btn_col1:
                if st.button("✅ Submit Answer",use_container_width=True,key=f"ssub{idx}"):
                    if not ua.strip():
                        st.error("❌ You cannot submit a blank answer! Please write something.")
                    else:
                        st.session_state.answers[idx]=ua; st.session_state.submitted_current=True
                        st.session_state.showing_result=True; st.session_state.q_t=None
                        with st.spinner("🤖 Evaluating..."):
                            try:
                                prompt=(
                                    f"You are a strict chemistry examiner for FSc/MDCAT Pakistan.\n"
                                    f"Question: {q['question']}\n"
                                    f"Model Answer: {q['model_answer']}\n"
                                    f"Student Answer: {ua}\n"
                                    f"Max Marks: {q['marks']}\n\n"
                                    f"STRICT RULES:\n"
                                    f"- If student answer is blank, empty, or just spaces: marks_awarded MUST be 0.\n"
                                    f"- If student answer is irrelevant or wrong: marks_awarded MUST be 0.\n"
                                    f"- Award marks only for correct chemistry content.\n"
                                    f"- Ignore minor spelling mistakes but list them.\n"
                                    f"- Be strict. Partial credit only if partially correct.\n\n"
                                    f"Respond ONLY with this JSON (no extra text):\n"
                                    f"{{\"marks_awarded\": 0, \"feedback\": \"...\", \"spelling_mistakes\": []}}"
                                )
                                er=ai.generate_content(prompt)
                                ev=safe_json(er.text)
                                ev["marks_awarded"]=min(int(ev.get("marks_awarded",0)),q["marks"])
                                if not ua.strip(): ev["marks_awarded"]=0
                                st.session_state.saq_eval[idx]=ev; st.session_state.score+=ev["marks_awarded"]
                                if ev["marks_awarded"]==q["marks"]: st.session_state.streak+=1; st.session_state.max_streak=max(st.session_state.streak,st.session_state.max_streak)
                                else: st.session_state.streak=0
                                if st.session_state.attempt_id and q.get("db_id"): sb.table("answers").insert({"attempt_id":st.session_state.attempt_id,"question_id":q["db_id"],"given_answer":ua,"marks_awarded":ev["marks_awarded"],"ai_feedback":ev["feedback"]}).execute()
                            except: st.session_state.saq_eval[idx]={"marks_awarded":0,"feedback":"Could not evaluate. Marks set to 0.","spelling_mistakes":[]}
                        st.rerun()
            with btn_col2:
                if idx not in skipped:
                    if st.button("⏭️ Skip",use_container_width=True,key=f"sskip{idx}"):
                        st.session_state.skipped_questions.append(idx)
                        st.session_state.current_q=pos+1
                        st.session_state.submitted_current=False
                        st.session_state.showing_result=False
                        st.session_state.q_t=None; st.session_state.time_up=False
                        st.session_state.hint_used={}
                        st.rerun()
        # Show result ONLY when showing_result is True
        elif st.session_state.showing_result:
            st.markdown(f"**Your answer:** {st.session_state.answers.get(idx,'')}")
            st.success(f"📖 **Model Answer:** {q['model_answer']}")
            if idx in st.session_state.saq_eval:
                ev=st.session_state.saq_eval[idx]; aw=ev["marks_awarded"]; mx=q["marks"]
                if aw==mx: st.success(f"🌟 **{aw}/{mx}** Excellent!")
                elif aw>0: st.warning(f"📝 **{aw}/{mx}** Partial")
                else: st.error(f"❌ **{aw}/{mx}**")
                st.info(f"💬 {ev['feedback']}")
                if ev.get("spelling_mistakes"): st.warning(f"🔤 {', '.join(ev['spelling_mistakes'])}")

    st.markdown("---")

    # Navigation buttons (only shown after submission)
    if st.session_state.submitted_current:
        remaining_in_order=len(order)-pos-1
        has_more=remaining_in_order>0 or len(skipped)>0
        if has_more:
            if st.button("➡️ Next Question",use_container_width=True):
                st.session_state.current_q=pos+1
                st.session_state.submitted_current=False
                # ── KEY FIX: clear showing_result so explanation never bleeds into next question ──
                st.session_state.showing_result=False
                st.session_state.q_t=None
                st.session_state.time_up=False
                st.session_state.hint_used={}
                st.rerun()
        else:
            if st.button("🏁 Finish & Results",use_container_width=True):
                st.session_state.quiz_done=True
                if st.session_state.attempt_id:
                    pct=(st.session_state.score/st.session_state.total_marks*100) if st.session_state.total_marks>0 else 0
                    sb.table("attempts").update({"score":st.session_state.score,"percentage":pct,"completed":True,"completed_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}).eq("id",st.session_state.attempt_id).execute()
                st.rerun()

    # Timer auto-refresh ONLY while question is active (not submitted, not time_up)
    if not st.session_state.submitted_current and not st.session_state.time_up:
        time.sleep(1)
        st.rerun()

# RESULTS
elif st.session_state.quiz_done:
    st.title("⚗️ ChemPrep AI"); st.markdown("## 🏆 Results"); st.markdown("---")
    questions=st.session_state.all_questions
    mcq_qs=[q for q in questions if q["type"]=="mcq"]; saq_qs=[q for q in questions if q["type"]=="saq"]
    tm=st.session_state.total_marks; sc=st.session_state.score; pct=(sc/tm*100) if tm>0 else 0
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Score",f"{sc}/{tm}")
    with c2: st.metric("%",f"{pct:.1f}%")
    with c3: st.metric("Questions",len(questions))
    with c4: st.metric("Streak 🔥",st.session_state.max_streak)
    if pct>=80: st.success("🌟 Excellent!")
    elif pct>=60: st.info("👍 Good!")
    elif pct>=40: st.warning("📚 More practice!")
    else: st.error("💪 Keep trying!")
    if st.session_state.bookmarked:
        st.markdown("### 🔖 Bookmarked")
        for i in st.session_state.bookmarked: st.info(f"Q{i+1}: {questions[i]['question']}")
    if mcq_qs:
        st.markdown("### 📋 MCQ Review")
        for i,q in enumerate(mcq_qs):
            sel=st.session_state.answers.get(i,"X")
            with st.expander(f"{'✅' if sel==q['answer'] else '❌'} MCQ {i+1}: {q['question']}"):
                for opt in q["options"]:
                    if opt.startswith(sel) and opt.startswith(q["answer"]): st.markdown(f"🟢 **{opt}** ✅")
                    elif opt.startswith(sel): st.markdown(f"🔴 **{opt}** ❌")
                    elif opt.startswith(q["answer"]): st.markdown(f"🟢 **{opt}** ✅")
                    else: st.markdown(f"⚪ {opt}")
                if q.get("explanation"): st.info(f"📖 {q['explanation']}")
    if saq_qs:
        st.markdown("### 📝 SAQ Review")
        off=len(mcq_qs)
        for i,q in enumerate(saq_qs):
            ri=off+i; ev=st.session_state.saq_eval.get(ri,{}); marks=ev.get("marks_awarded",0)
            with st.expander(f"{'🌟' if marks==q['marks'] else '📝' if marks>0 else '❌'} SAQ {i+1}: {q['question']} — {marks}/{q['marks']}"):
                st.markdown(f"**Your Answer:** {st.session_state.answers.get(ri,'—')}")
                st.success(f"**Model Answer:** {q['model_answer']}")
                if ev: st.info(f"💬 {ev.get('feedback','')}")
    st.markdown("---")
    if st.button("🔄 Back to Home",use_container_width=True):
        st.session_state.quiz_started=False; st.session_state.quiz_done=False
        st.session_state.page="student_home" if st.session_state.role=="student" else "teacher_dashboard"; st.rerun()
