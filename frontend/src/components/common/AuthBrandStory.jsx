import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, GraduationCap, ShieldCheck } from "lucide-react";
import "./AuthBrandStory.css";

const stories = [
  { title: "Spot the signal.", icon: ShieldCheck, tone: "violet" },
  { title: "Understand engagement.", icon: Activity, tone: "lavender" },
  { title: "Support every learner.", icon: GraduationCap, tone: "teal" },
  { title: "Turn insight into action.", icon: ArrowUpRight, tone: "violet" },
];

export default function AuthBrandStory({ signup = false }) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer;
    const startCycling = () => {
      if (motionPreference.matches || timer) return;
      timer = window.setInterval(() => {
        if (!document.hidden) setActive((index) => (index + 1) % stories.length);
      }, 2600);
    };
    const updateMotion = () => {
      window.clearInterval(timer);
      timer = undefined;
      if (motionPreference.matches) setActive(0);
      else startCycling();
    };

    startCycling();
    motionPreference.addEventListener?.("change", updateMotion);
    return () => {
      window.clearInterval(timer);
      motionPreference.removeEventListener?.("change", updateMotion);
    };
  }, []);

  const story = stories[active];
  const Icon = story.icon;

  return (
    <div className={`auth-hero-story ${signup ? "is-signup" : ""}`}>
      <span className="story-kicker">
        <i /> LEARNER SUCCESS, IN FOCUS
      </span>
      <div className={`auth-hero-message tone-${story.tone}`} key={active}>
        <span className="auth-hero-icon" aria-hidden="true"><Icon /></span>
        <h1>{story.title}</h1>
      </div>
      <p>
        {signup
          ? "Bring engagement signals into view and give your team a clearer path to learner success."
          : "Understand engagement, identify risk early, and turn insight into meaningful action."}
      </p>
      <div className="story-proof">
        <div className="proof-avatars" aria-hidden="true">
          <b>J</b><b>M</b><b>A</b><b>+</b>
        </div>
        <span>
          {signup ? <>A clearer picture of<br />every learner journey</> : <>Designed for teams who care<br />about every learner journey</>}
        </span>
      </div>
    </div>
  );
}
