from unittest import mock

from django.test import SimpleTestCase

from . import chatbot


class EmergencyDetectionTests(SimpleTestCase):
    def test_english_variants(self):
        for text in ["my father is clutching his chest", "she is not waking up", "I can't catch my breath",
                     "he swallowed a lot of pills", "a snake bit him", "coughing up blood"]:
            self.assertTrue(chatbot.is_emergency(text), text)

    def test_roman_urdu_and_urdu(self):
        for text in ["mujhe saans nahi aa rahi", "seene mein dard hai", "bachay ne zeher pi liya", "khoon ruk nahi raha",
                     "مجھے سانس نہیں آ رہی", "سینے میں شدید درد ہے", "بچی بے ہوش ہو گئی ہے"]:
            self.assertTrue(chatbot.is_emergency(text), text)

    def test_spelling_variation(self):
        self.assertTrue(chatbot.is_emergency("mujhe sans nahi aa rahi"))
        self.assertTrue(chatbot.is_emergency("CHEST PAIN!!!"))

    def test_no_false_alarms_from_substrings(self):
        for text in ["I will be ill if I skip breakfast", "a brush stroke on my painting", "my keystroke counter",
                     "what a stroke of luck", "my heart is broken after a breakup", "I have a mild headache"]:
            self.assertFalse(chatbot.is_emergency(text), text)

    def test_self_harm_gets_its_own_supportive_reply(self):
        text, urgency, source = chatbot.get_reply("I want to kill myself")
        self.assertEqual((urgency, source), ("emergency", "builtin"))
        self.assertIn("1122", text)
        self.assertNotIn("medical emergency", text.lower())

    def test_emergency_reply_matches_language(self):
        self.assertIn("Foran", chatbot.get_reply("mujhe saans nahi aa rahi")[0])
        self.assertIn("فوراً", chatbot.get_reply("مجھے سانس نہیں آ رہی")[0])


class ScopeTests(SimpleTestCase):
    def test_roman_urdu_health_is_not_refused(self):
        with mock.patch.object(chatbot, "_call_openai", side_effect=RuntimeError("down")):
            text, _, source = chatbot.get_reply("mujhe do din se bukhar hai")
        self.assertEqual(source, "builtin")
        self.assertNotIn("only help with", text)

    def test_health_message_with_place_word_is_not_a_map_link(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="Rest and drink water."):
            text, _, source = chatbot.get_reply("the pharmacy gave me tablets and now my stomach hurts")
        self.assertEqual(source, "ai")

    def test_near_me_still_returns_map_links(self):
        self.assertIn("google.com/maps", chatbot.get_reply("pharmacy near me")[0])

    def test_off_topic_never_reaches_the_ai(self):
        with mock.patch.object(chatbot, "_call_openai") as call:
            chatbot.get_reply("write a python function to sort a list")
            call.assert_not_called()


class EmotionalDistressTests(SimpleTestCase):
    """Regression: H039 'my heart is broken after a breakup' was refused as off-topic."""
    H039 = "my heart is broken after a breakup, how do I cope"

    def test_h039_is_health_related_and_not_an_emergency(self):
        self.assertTrue(chatbot.is_emotional_distress(self.H039))
        self.assertTrue(chatbot.is_health_related(self.H039))
        self.assertFalse(chatbot.is_clearly_off_topic(self.H039))
        self.assertFalse(chatbot.is_emergency(self.H039))
        self.assertFalse(chatbot.is_self_harm(self.H039))

    def test_model_off_topic_refusal_becomes_a_supportive_answer(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="OFF_TOPIC"):
            text, urgency, _ = chatbot.get_reply(self.H039)
        self.assertEqual(urgency, "routine")
        self.assertFalse(text.startswith(chatbot.OUT_OF_SCOPE_REPLY))
        self.assertIn("sorry", text.lower())

    def test_offline_fallback_is_supportive_not_a_refusal(self):
        with mock.patch.object(chatbot, "_call_openai", side_effect=RuntimeError("down")):
            text, _, source = chatbot.get_reply(self.H039)
        self.assertEqual(source, "builtin")
        self.assertFalse(text.startswith(chatbot.OUT_OF_SCOPE_REPLY))
        self.assertIn("sorry", text.lower())

    def test_model_answer_is_passed_through(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="[URGENCY: routine]\nBreakups are hard."):
            text, _, source = chatbot.get_reply(self.H039)
        self.assertEqual(source, "ai")
        self.assertIn("Breakups are hard.", text)

    def test_distress_does_not_open_the_off_topic_gate(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="OFF_TOPIC"):
            text, _, _ = chatbot.get_reply("write a python script about my breakup")
        self.assertTrue(text.startswith(chatbot.OUT_OF_SCOPE_REPLY))

    def test_self_harm_and_emergency_rules_still_win(self):
        for msg in ("my heart is broken and I want to kill myself", "heartbroken, I want to end my life",
                    "I'm heartbroken and I have crushing chest pain"):
            with mock.patch.object(chatbot, "_call_openai") as call:
                text, urgency, source = chatbot.get_reply(msg)
            call.assert_not_called()
            self.assertEqual((urgency, source), ("emergency", "builtin"), msg)
            self.assertIn("1122", text)


class IndirectSelfHarmTests(SimpleTestCase):
    """Indirect phrasings must get the self-harm reply and must never reach the model."""

    ENGLISH = [
        "I don't want to live anymore", "i dont want to live", "I do not want to live", "I no longer want to live",
        "I don't want to be alive", "I don't want to be here anymore", "I dont want to be here any more",
        "there is no reason to live", "I have nothing to live for", "there's no point in living",
        "life is not worth living", "I'm tired of living", "everyone would be better off without me",
        "my family would be better off dead", "they would be better off if I was dead",
        "I can't go on like this", "I can't go on anymore", "I can't do this anymore", "I cannot do this any more",
        "I wish I wasn't alive", "I wish I wasnt alive", "I wish I was dead", "I wish I could disappear",
        "I wish I could just disappear", "I wish I was never born", "I keep thinking about ending it all",
        "my heart is broken after a breakup and I don't want to live",
        "My heart is broken after a breakup and I don’t want to live",  # curly apostrophe
        "I DON'T WANT TO LIVE ANYMORE", "i dooon't want to liiive",
    ]
    ROMAN_UR = [
        "ab mujhe jeene ka dil nahi karta", "main jeena nahin chahta", "mujhe jeena nhi chahiye, main jeena nhi chahti",
        "main jina nahi chahta", "mujhe jeene ki koi wajah nahi", "kash main mar jaun", "kash main mar jata",
        "mere bina sab behtar hain", "mere bagair sab theek ho jayega", "mujhe maut chahiye", "meri zindagi khatam ho jaye",
        "main mar jana chahta hoon", "main zindagi se thak gaya hoon, zindagi se tang aa gaya hoon",
        "mujhe marne ka dil karta hai", "main khud ko khatam kar loon",
    ]
    URDU = [
        "مجھے جینے کا دل نہیں کرتا", "میں مر جانا چاہتا ہوں", "میں مر جانا چاہتی ہوں", "کاش میں مر جاتا",
        "کاش میں مر جاتی", "میرے بغیر سب بہتر ہوں گے", "مجھے موت چاہیے", "اب میں زندہ نہیں رہنا چاہتی",
        "مجھے جینے کی کوئی وجہ نہیں", "میں زندگی سے تنگ آ گیا ہوں", "میں خود کو ختم کر دوں گا",
    ]
    NOT_SELF_HARM = [
        "I don't want to live in Karachi", "I don't want to live with my roommate", "how long can a person live without food",
        "my grandfather doesn't want to live alone", "my grandmother doesn't want to live with us",
        "I don't want to live near the highway because of the noise", "I can't go on the school trip because of my fever",
        "I can't do this exercise anymore, my knee hurts", "I don't want to be here at the clinic all day, how long is the wait",
        "what is the life expectancy of someone with diabetes", "is my diet better off without sugar",
        "my mother wants to live with us after her surgery", "mujhe Lahore mein rehna nahi pasand",
        "jeene ke liye kitna paani peena chahiye", "انسان پانی کے بغیر کتنا جی سکتا ہے", "مجھے کراچی میں رہنا پسند نہیں",
    ]

    def _assert_self_harm(self, message):
        with mock.patch.object(chatbot, "_call_openai") as call:
            text, urgency, source = chatbot.get_reply(message)
        call.assert_not_called()
        self.assertEqual((urgency, source), ("emergency", "builtin"), message)
        self.assertTrue(text.startswith(chatbot.SELF_HARM_REPLY), message)
        self.assertIn("1122", text)

    def test_english_indirect_phrasings(self):
        for msg in self.ENGLISH:
            with self.subTest(msg=msg):
                self._assert_self_harm(msg)

    def test_roman_urdu_indirect_phrasings(self):
        for msg in self.ROMAN_UR:
            with self.subTest(msg=msg):
                self._assert_self_harm(msg)

    def test_urdu_indirect_phrasings(self):
        for msg in self.URDU:
            with self.subTest(msg=msg):
                self._assert_self_harm(msg)

    def test_reply_language_matches(self):
        self.assertIn("Aap ki hifazat", chatbot.get_reply("ab mujhe jeene ka dil nahi karta")[0])
        self.assertIn("آپ کی حفاظت", chatbot.get_reply("مجھے جینے کا دل نہیں کرتا")[0])

    def test_look_alikes_are_not_flagged(self):
        for msg in self.NOT_SELF_HARM:
            with self.subTest(msg=msg):
                self.assertFalse(chatbot.is_self_harm(msg), msg)
                with mock.patch.object(chatbot, "_call_openai", return_value="Some general information."):
                    text, urgency, _ = chatbot.get_reply(msg)
                self.assertNotEqual(urgency, "emergency", msg)
                self.assertFalse(text.startswith(chatbot.SELF_HARM_REPLY), msg)

    def test_in_this_world_is_not_treated_as_housing(self):
        self.assertTrue(chatbot.is_self_harm("I don't want to live in this world anymore"))
        self.assertTrue(chatbot.is_self_harm("I don't want to live in this life"))


class LiveReplyParsingTests(SimpleTestCase):
    def test_urgency_tag_is_read_and_removed(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="[URGENCY: urgent]\nSee a doctor soon."):
            text, urgency, _ = chatbot.get_reply("my knee has been swollen for a week")
        self.assertEqual(urgency, "urgent")
        self.assertNotIn("[URGENCY", text)

    def test_model_emergency_without_1122_gets_emergency_prefix(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="[URGENCY: emergency]\nGo to hospital."):
            text, urgency, _ = chatbot.get_reply("I feel very strange and weak on one side")
        self.assertEqual(urgency, "emergency")
        self.assertIn("1122", text)

    def test_missing_tag_falls_back_to_marker_detection(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="You should see a doctor soon."):
            _, urgency, _ = chatbot.get_reply("my knee has been swollen for a week")
        self.assertEqual(urgency, "urgent")

    def test_bare_off_topic_word_is_replaced(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="OFF_TOPIC"):
            text, _, _ = chatbot.get_reply("tell me about my health insurance paperwork")
        self.assertIn("health questions", text)
