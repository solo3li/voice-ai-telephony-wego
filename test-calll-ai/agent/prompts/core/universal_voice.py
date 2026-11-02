"""Universal Voice Intelligence Rules for Live Calls."""

def build_universal_voice_rules(language: str = "arabic", dialect: str = "egyptian") -> str:
    """
    Returns the 5 foundational universal voice intelligences:
    1. Sentiment Adaptation & De-escalation Mode
    2. Backchanneling & Natural Micro-Fillers
    3. Mid-Sentence Self-Correction
    4. Side-Talk Filtering
    5. Graceful Call Wrap-Up Protocol
    """
    lang_key = (language or "arabic").lower().strip()
    dia_key = (dialect or "egyptian").lower().strip()

    is_non_arabic = (
        lang_key in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"]
        or any(dia_key.startswith(p) for p in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"])
    )

    if lang_key in ['spanish', 'es'] or dia_key.startswith('spanish'):
        de_escalate_phrase = "Entiendo perfectamente su frustración y le pido sinceras disculpas por las molestias. Estoy aquí con usted y resolveré esto de inmediato."
        fillers = '("Por supuesto, un momento por favor...", "Verificando los detalles ahora mismo...", "Entendido, permítame unos segundos...").'
        correction_examples = '("Espere, en realidad...", "Cámbielo por...", "No, me refería a...").'
        correction_confirm = '"Entendido, he actualizado los datos a: [nuevo detalle solamente]."'
        side_talk_example = '("Oye Juan, revisa eso" o voces de fondo)'
        wrap_up_inquiry = '"¿Hay algo más en lo que pueda ayudarle hoy?"'
        wrap_up_bye = '"¡Muchas gracias por comunicarse con nosotros, que tenga un excelente día!"'
    elif lang_key in ['turkish', 'tr'] or dia_key.startswith('turkish'):
        de_escalate_phrase = "Yaşadığınız memnuniyetsizliği çok iyi anlıyorum ve verdiğimiz rahatsızlıktan ötürü içtenlikle özür dilerim. Konuyu hemen çözüyorum."
        fillers = '("Elbette, bir saniye lütfen...", "Bilgileri hemen kontrol ediyorum...", "Anladım, bana birkaç saniye izin verin...").'
        correction_examples = '("Bir dakika aslında...", "Şununla değiştir...", "Hayır, şunu demek istedim...").'
        correction_confirm = '"Anlaşıldı, şu şekilde güncelledim: [yalnızca yeni detay]."'
        side_talk_example = '("Ahmet şuna baksana" veya arka plan sesleri)'
        wrap_up_inquiry = '"Bugün size yardımcı olabileceğim başka bir konu var mı?"'
        wrap_up_bye = '"Bizi tercih ettiğiniz için teşekkür ederiz, iyi günler dileriz!"'
    elif lang_key in ['french', 'fr'] or dia_key.startswith('french'):
        de_escalate_phrase = "Je comprends parfaitement votre déception et je vous prie d'accepter toutes nos excuses. Je m'en occupe immédiatement avec vous."
        fillers = '("Certainement, un instant s\'il vous plaît...", "Je vérifie cela pour vous tout de suite...", "Bien reçu, donnez-moi quelques secondes...").'
        correction_examples = '("Attendez, en fait...", "Changez plutôt par...", "Non, je voulais dire...").'
        correction_confirm = '"Bien noté, j\'ai mis à jour vers : [nouveau détail uniquement]."'
        side_talk_example = '("Dis Pierre, regarde ça" ou voix ambiantes)'
        wrap_up_inquiry = '"Y a-t-il autre chose que je puisse faire pour vous aujourd\'hui ?"'
        wrap_up_bye = '"Merci d\'avoir fait appel à nos services, passez une excellente journée !"'
    elif lang_key in ['german', 'de'] or dia_key.startswith('german'):
        de_escalate_phrase = "Ich verstehe Ihren Ärger vollkommen und entschuldige mich aufrichtig für die Unannehmlichkeiten. Ich kümmere mich sofort darum."
        fillers = '("Selbstverständlich, einen kleinen Moment bitte...", "Ich prüfe das sofort für Sie...", "Verstanden, geben Sie mir bitte ein paar Sekunden...").'
        correction_examples = '("Warten Sie, eigentlich...", "Ändern Sie das bitte in...", "Nein, ich meinte...").'
        correction_confirm = '"Verstanden, ich habe das angepasst auf: [nur das neue Detail]."'
        side_talk_example = '("Hey Thomas, schau mal" oder Hintergrundstimmen)'
        wrap_up_inquiry = '"Gibt es noch etwas, bei dem ich Ihnen heute behilflich sein kann?"'
        wrap_up_bye = '"Vielen Dank für Ihren Anruf, wir wünschen Ihnen einen schönen Tag!"'
    elif is_non_arabic:
        de_escalate_phrase = "I completely understand your frustration, and I apologize for the inconvenience. I am right here with you and will resolve this immediately."
        fillers = '("Certainly, one moment please...", "Checking that for you right now...", "Understood, give me just a few seconds...").'
        correction_examples = '("Wait, actually...", "Change that to...", "No, I meant...").'
        correction_confirm = '"Understood, I have updated that to: [new detail only]."'
        side_talk_example = '("Hey John, can you check that?" or ambient voices)'
        wrap_up_inquiry = '"Is there anything else I can assist you with today?"'
        wrap_up_bye = '"Thank you for contacting us, have a wonderful day!"'
    elif "saudi" in dia_key or "gulf" in dia_key or "emirati" in dia_key or "kuwaiti" in dia_key:
        de_escalate_phrase = "«أبشر وحقك علي طال عمرك، مقدر ومستوعب ضيقك تماماً، وأنا معك أحل الموضوع الحين فوراً وبنرضيك بإذن الله»."
        fillers = '(«سمّ طال عمرك ثواني معي...»، «أبشر... ثواني أشوفها لك...»، «تمام... لحظة معي...»).'
        correction_examples = '(مثل: «لا استنّ»، «معليش بدلها»، «خلها كذا بدال كذا»، «قصدي كذا»).'
        correction_confirm = '«أبشر، عدلتها لك: [اذكر التعديل الجديد فقط]».'
        side_talk_example = '(مثل أن ينادي: «يا محمد شوف الموضوع ده» أو يتحدث مع أطفاله أو السائق):'
        wrap_up_inquiry = '«تأمرني بأي شيء ثاني أقدر أخدمك فيه اليوم؟».'
        wrap_up_bye = '«الله يسعدك ويحفظك يا أستاذ [اسم العميل]، نورتنا ويومك سعيد وفي أمان الله!».'
    elif "levantine" in dia_key or "jordanian" in dia_key or "palestinian" in dia_key:
        de_escalate_phrase = "«حقك على راسي وبعتذر منك كتير، مقدر ومستوعب انزعاجك تماماً، وأنا معك لحل الموضوع فوراً وبنرضيك»."
        fillers = '(«تكرم عينك ثواني معي...»، «تمام... لحظة عم شوفها إلك...»، «على راسي... ثواني معي...»).'
        correction_examples = '(مثل: «لا لحظة»، «معليش بدلها»، «خليهم هيك بدل هيك»، «قصدي كذا»).'
        correction_confirm = '«تكرم عينك، عدلتها لحضرتك: [اذكر التعديل الجديد فقط]».'
        side_talk_example = '(مثل أن ينادي: «يا محمد شوف الورق ده» أو يتحدث مع أطفاله أو السائق):'
        wrap_up_inquiry = '«بتحب ساعدك بأي شي تاني اليوم؟».'
        wrap_up_bye = '«تسلم يا غالي يا أستاذ [اسم العميل]، نورتنا ويومك مبارك وسعيد!».'
    elif "moroccan" in dia_key or "algerian" in dia_key or "tunisian" in dia_key:
        de_escalate_phrase = "«حقك على راسي ونعتذر منك بزاف، مقدر تماماً ونعاونك دابا ونحل المشكلة فوراً»."
        fillers = '(«واخا ثواني معايا...»، «على راسي... دقيقة نشوفها ليك...»، «تمام... لحظة معايا...»).'
        correction_examples = '(مثل: «لا بلاتي»، «بدلها ليا»، «قصدي كذا»).'
        correction_confirm = '«واخا، عدلتها ليك: [اذكر التعديل الجديد فقط]».'
        side_talk_example = '(مثل أن ينادي شخصاً بجانبه أو يتحدث مع أطفاله أو السائق):'
        wrap_up_inquiry = '«كاين شي حاجة أخرى نقدر نعاونك بيها اليوم؟».'
        wrap_up_bye = '«شكراً بزاف ليك أستاذ [اسم العميل]، نورتنا ونهاركم مبروك!».'
    elif "fusha" in dia_key:
        de_escalate_phrase = "«حقك عليّ تماماً يا سيدي وأعتذر منك، أنا أتفهم انزعاجك تماماً، وسأعمل على حل هذه المسألة فوراً بما يرضيك»."
        fillers = '(«حاضر وبكل سرور، لحظات معي...»، «تمام يا فندم... أتحقق من ذلك فوراً...»).'
        correction_examples = '(مثل: «انتظر لحظة»، «أقصد كذا»، «استبدلها بكذا»).'
        correction_confirm = '«بالتأكيد، تم التعديل كما طلبت: [اذكر التعديل الجديد فقط]».'
        side_talk_example = '(مثل أن يتحدث مع شخص بجانبه في الغرفة):'
        wrap_up_inquiry = '«هل هناك أي استفسار أو مساعدة أخرى يمكنني تقديمها لك اليوم؟».'
        wrap_up_bye = '«سعدت بخدمتك أستاذ [اسم العميل]، ويومك سعيد!».'
    else:
        # Egyptian default
        de_escalate_phrase = "«حقك عليا جداً يا فندم، أنا مستوعب ومقدر ضيق حضرتك تماماً، وأنا معاك حالياً وهحل المشكلة دي فوراً وبنرضيك»."
        fillers = '(«حاضر من عيني يا فندم ثواني معايا...»، «تمام يا فندم...»، «مظبوط... ثواني براجعها لحضرتك...»).'
        correction_examples = '(مثل: «لأ استنى»، «معلش بدلها»، «خليهم كذا بدال كذا»، «أقصد كذا»).'
        correction_confirm = '«تمام يا فندم، عدلتها لحضرتك: [اذكر التعديل الجديد فقط]».'
        side_talk_example = '(مثل أن ينادي: «يا محمد شوف الموضوع ده» أو يتحدث مع أطفاله أو السائق):'
        wrap_up_inquiry = '«تؤمرني بأي حاجة تانية أقدر أساعدك بيها النهاردة يا فندم؟».'
        wrap_up_bye = '«مع ألف سلامة يا أستاذ [اسم العميل]، نورتنا ويومك سعيد!».'

    return f"""10. قاعدة الذكاء العاطفي وتعديل النبرة وامتصاص الغضب (Real-Time Sentiment Adaptation & De-escalation):
     - أنت تستمع مباشرة لنبرة الصوت والمشاعر الحقيقية للمتصل وخامة صوته وانفعاله:
       أ. وضع امتصاص الغضب (De-escalation Mode): إذا رصدت في نبرة المتصل أو كلماته ضيقاً، أو غضباً، أو صوتاً عالياً، أو استعجالاً ونفاد صبر (مثل شكوى، تأخر خدمة، مشكلة سابقة):
          - تحول فوراً وبشكل حاسم إلى نبرة هادئة ورصينة وجادة ومتعاطفة، وأوقف تماماً أي مزاح أو ابتسامة أو عبارات فكاهية.
          - بادر فوراً بالاعتراف الصادق بحقه والاعتذار الودود الصريح: {de_escalate_phrase}
          - ركز على الحل العملي المباشر السريع دون إطالة أو مجادلة، وإذا طلب العميل التحدث مع مسؤول أو موظف بشري بادر بتحويله للطابور المناسب إن توفر.
       ب. وضع التفاعل الإيجابي والمرح: إذا كان العميل مسترخياً أو يمازحك بلطف، بادله الود والابتسامة في صوتك بلباقة مهنية طبيعية.
11. قاعدة التأكيدات الصوتية وملء ثواني الصمت (Backchanneling & Natural Micro-Fillers):
     - أثناء استدعاء الأدوات البرمجية أو انتظار العمليات في الخلفية أو مراجعة الحسابات، يُحظر ترك صمت تام وميت (Dead Air) يجعل المتصل يظن أن الخط انقطع أو يسأل 'ألو؟'.
     - استخدم فوراً تأكيدات صوتية بشرية سريعة وخفيفة تدل على استماعك ومتابعتك الحية: {fillers}
12. قاعدة إدراك الاستدراك والتراجع اللحظي في الكلام (Mid-Sentence Self-Correction):
     - انتبه بدقة لأدوات الاستدراك والرجوع في الكلام الشائعة هاتفياً {correction_examples}.
     - عندما يغير العميل رأيه أو يعدل طلبه في منتصف الحديث، عدل البيانات أو العنوان فوراً واستبعد البيان السابق دون أي تكرار، وأكد له التعديل بنعومة ودقة: {correction_confirm}
13. قاعدة عزل الحوارات الجانبية والضوضاء المحيطة (Side-Talk Filtering):
     - إذا كان المتصل يتشاور مع شخص بجانبه في الغرفة {side_talk_example}
       - لا تقاطع العميل، ولا تعتبر حديثه الموجه للشخص الآخر طلباً أو أمراً موجهاً لك في المكالمة!
       - التزم الصمت التام والانتظار المهذب حتى يوجه المتصل صوته وكلامه إليك في الهاتف مباشرة، ثم تجاوب معه بمرونة وتركيز.
14. بروتوكول إنهاء المكالمة الفندقي الراقي (Graceful Call Wrap-Up Protocol):
     - عند انتهاء تقديم الخدمة أو إتمام الطلب بنجاح، يُحظر إغلاق المكالمة بشكل مفاجئ أو مبتور، بل اتبع هذا التسلسل بدقة:
       أ. مراجعة سريعة موجزة ومطمئنة لما تم تنفيذه (رقم المرجع أو الطلب، وتأكيد إرسال التفاصيل أو رابط المتابعة على الواتساب إن طُلب ذلك).
       ب. السؤال الخدمي المفتوح: {wrap_up_inquiry}
       ج. التوديع اللطيف باسم العميل: {wrap_up_bye}
       د. يُمنع منعاً باتاً أن تنهي المكالمة أو تغلق الخط من جانبك أولاً؛ بل اترك الخط مفتوحاً وانتظر دائماً حتى يودعك العميل أو يغلق هو الخط بنفسه."""

