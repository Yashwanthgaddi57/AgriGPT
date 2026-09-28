"use client";

/**
 * Lightweight i18n for dashboard chrome. Persisted to localStorage; defaults
 * to the profile language when available. AI answers adapt via the language
 * directive sent with each chat message — this covers the UI labels.
 */
import * as React from "react";

export type Lang = "en" | "hi" | "te" | "ta" | "kn" | "mr";

const DICT: Record<Exclude<Lang, "en">, Record<string, string>> = {
  hi: {
    // Bottom navigation + mobile chrome
    Home: "होम",
    Farm: "खेत",
    Health: "सेहत",
    Copilot: "सहायक",
    More: "और",
    "All pages": "सभी पेज",
    "My Farm": "मेरा खेत",
    "Ask AgriGPT": "अग्रीजीपीटी से पूछें",
    "Farm Log": "खेत दैनिकी",
    Overview: "अवलोकन",
    "Crop Advisor": "फसल सलाहकार",
    "Plan My Farm": "मेरा खेत योजना",
    "Disease Scan": "रोग जाँच",
    "Profit Predictor": "लाभ अनुमान",
    "Profit Calculator": "लाभ कैलकुलेटर",
    "Market Intelligence": "बाज़ार जानकारी",
    Weather: "मौसम",
    "Vendors Near Me": "पास के विक्रेता",
    "AI Copilot": "एआई सहायक",
    Analytics: "विश्लेषण",
    Profile: "प्रोफ़ाइल",
    "Sign out": "साइन आउट",
    Notifications: "सूचनाएँ",
    "New conversation": "नई बातचीत",
    "Weather, disease, market and profit alerts": "मौसम, रोग, बाज़ार और लाभ की चेतावनियाँ",
    "No notifications yet.": "अभी कोई सूचना नहीं।",
  },
  te: {
    // Bottom navigation + mobile chrome
    Home: "హోమ్",
    Farm: "పొలం",
    Health: "పంట ఆరోగ్యం",
    Copilot: "సహాయకుడు",
    More: "మరిన్ని",
    "All pages": "అన్ని పేజీలు",
    "My Farm": "నా పొలం",
    "Ask AgriGPT": "అగ్రిజీపీటీని అడగండి",
    "Farm Log": "పొలం నిర్వహణ",
    Overview: "అవలోకనం",
    "Crop Advisor": "పంట సలహాదారు",
    "Plan My Farm": "నా పొలం ప్రణాళిక",
    "Disease Scan": "తెగులు పరీక్ష",
    "Profit Predictor": "లాభ అంచనా",
    "Profit Calculator": "లాభ కాలిక్యులేటర్",
    "Market Intelligence": "మార్కెట్ సమాచారం",
    Weather: "వాతావరణం",
    "Vendors Near Me": "సమీప విక్రేతలు",
    "AI Copilot": "ఏఐ సహాయకుడు",
    Analytics: "విశ్లేషణలు",
    Profile: "ప్రొఫైల్",
    "Sign out": "సైన్ అవుట్",
    Notifications: "నోటిఫికేషన్లు",
    "New conversation": "కొత్త సంభాషణ",
    "Weather, disease, market and profit alerts": "వాతావరణ, తెగులు, మార్కెట్ మరియు లాభ హెచ్చరికలు",
    "No notifications yet.": "ఇంకా నోటిఫికేషన్లు లేవు.",
  },
  ta: {
    // Bottom navigation + mobile chrome
    Home: "முகப்பு",
    Farm: "பண்ணை",
    Health: "பயிர் நலம்",
    Copilot: "உதவியாளர்",
    More: "மேலும்",
    "All pages": "அனைத்து பக்கங்கள்",
    "My Farm": "என் பண்ணை",
    "Ask AgriGPT": "அக்ரிஜிபிடியிடம் கேளுங்கள்",
    "Farm Log": "பண்ணை பதிவேடு",
    Overview: "மேலோட்டம்",
    "Crop Advisor": "பயிர் ஆலோசகர்",
    "Plan My Farm": "என் பண்ணை திட்டம்",
    "Disease Scan": "நோய் பரிசோதனை",
    "Profit Predictor": "லாப கணிப்பு",
    "Profit Calculator": "லாப கால்குலேட்டர்",
    "Market Intelligence": "சந்தை தகவல்",
    Weather: "வானிலை",
    "Vendors Near Me": "அருகில் உள்ள விற்பனையாளர்",
    "AI Copilot": "ஏஐ உதவியாளர்",
    Analytics: "பகுப்பாய்வு",
    Profile: "சுயவிவரம்",
    "Sign out": "வெளியேறு",
    Notifications: "அறிவிப்புகள்",
    "New conversation": "புதிய உரையாடல்",
    "Weather, disease, market and profit alerts": "வானிலை, நோய், சந்தை மற்றும் லாப எச்சரிக்கைகள்",
    "No notifications yet.": "இன்னும் அறிவிப்புகள் இல்லை.",
  },
  kn: {
    // Bottom navigation + mobile chrome
    Home: "ಮುಖಪುಟ",
    Farm: "ಜಮೀನು",
    Health: "ಬೆಳೆ ಆರೋಗ್ಯ",
    Copilot: "ಸಹಾಯಕ",
    More: "ಇನ್ನಷ್ಟು",
    "All pages": "ಎಲ್ಲಾ ಪುಟಗಳು",
    "My Farm": "ನನ್ನ ಜಮೀನು",
    "Ask AgriGPT": "ಅಗ್ರಿಜಿಪಿಟಿಯನ್ನು ಕೇಳಿ",
    "Farm Log": "ಜಮೀನು ದಿನಚರಿ",
    Overview: "ಅವಲೋಕನ",
    "Crop Advisor": "ಬೆಳೆ ಸಲಹೆಗಾರ",
    "Plan My Farm": "ನನ್ನ ಜಮೀನು ಯೋಜನೆ",
    "Disease Scan": "ರೋಗ ಪರಿಶೀಲನೆ",
    "Profit Predictor": "ಲಾಭ ಮುನ್ನೋಟ",
    "Profit Calculator": "ಲಾಭ ಕ್ಯಾಲ್ಕುಲೇಟರ್",
    "Market Intelligence": "ಮಾರುಕಟ್ಟೆ ಮಾಹಿತಿ",
    Weather: "ಹವಾಮಾನ",
    "Vendors Near Me": "ಹತ್ತಿರದ ವಿಕ್ರೇತರು",
    "AI Copilot": "ಏಐ ಸಹಾಯಕ",
    Analytics: "ವಿಶ್ಲೇಷಣೆ",
    Profile: "ಪ್ರೊಫೈಲ್",
    "Sign out": "ಸೈನ್ ಔಟ್",
    Notifications: "ಅಧಿಸೂಚನೆಗಳು",
    "New conversation": "ಹೊಸ ಸಂಭಾಷಣೆ",
    "Weather, disease, market and profit alerts": "ಹವಾಮಾನ, ರೋಗ, ಮಾರುಕಟ್ಟೆ ಮತ್ತು ಲಾಭ ಎಚ್ಚರಿಕೆಗಳು",
    "No notifications yet.": "ಇನ್ನೂ ಅಧಿಸೂಚನೆಗಳಿಲ್ಲ.",
  },
  mr: {
    // Bottom navigation + mobile chrome
    Home: "मुख्यपृष्ठ",
    Farm: "शेत",
    Health: "पीक आरोग्य",
    Copilot: "सहाय्यक",
    More: "अधिक",
    "All pages": "सर्व पृष्ठे",
    "My Farm": "माझे शेत",
    "Ask AgriGPT": "अ‍ॅग्रिजीपीटीला विचारा",
    "Farm Log": "शेत डायरी",
    Overview: "आढावा",
    "Crop Advisor": "पीक सल्लागार",
    "Plan My Farm": "माझ्या शेताची योजना",
    "Disease Scan": "रोग तपासणी",
    "Profit Predictor": "नफा अंदाज",
    "Profit Calculator": "नफा कॅल्क्युलेटर",
    "Market Intelligence": "बाजार माहिती",
    Weather: "हवामान",
    "Vendors Near Me": "जवळचे विक्रेते",
    "AI Copilot": "एआय सहाय्यक",
    Analytics: "विश्लेषण",
    Profile: "प्रोफाइल",
    "Sign out": "साइन आउट",
    Notifications: "सूचना",
    "New conversation": "नवीन संभाषण",
    "Weather, disease, market and profit alerts": "हवामान, रोग, बाजार आणि नफा सूचना",
    "No notifications yet.": "अजून सूचना नाहीत.",
  },
};

const LangContext = React.createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (s: string) => string;
}>({ lang: "en", setLang: () => {}, t: (s) => s });

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = React.useState<Lang>("en");

  React.useEffect(() => {
    const saved = localStorage.getItem("agrigpt-lang") as Lang | null;
    if (saved && (saved === "en" || saved in DICT)) setLangState(saved);
  }, []);

  const setLang = React.useCallback((l: Lang) => {
    setLangState(l);
    localStorage.setItem("agrigpt-lang", l);
  }, []);

  const t = React.useCallback(
    (s: string) => (lang !== "en" ? DICT[lang][s] ?? s : s),
    [lang]
  );

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>
  );
}

export function useLang() {
  return React.useContext(LangContext);
}

/** Small language switcher for the dashboard header. */
export function LangSwitch() {
  const { lang, setLang } = useLang();
  const options: { value: Lang; label: string }[] = [
    { value: "en", label: "EN" },
    { value: "te", label: "తె" },
    { value: "hi", label: "हिं" },
    { value: "ta", label: "த" },
    { value: "kn", label: "ಕ" },
    { value: "mr", label: "म" },
  ];
  return (
    <div className="flex items-center gap-0.5 rounded-full border p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => setLang(o.value)}
          className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
            lang === o.value ? "bg-leaf-600 text-white" : "text-muted-foreground hover:text-foreground"
          }`}
          aria-label={`Language: ${o.label}`}
          title={`Language: ${o.label}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
