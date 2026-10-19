import { useEffect, useState } from 'react'

// the first thing you see. its in spotter colors cuz this is for spotter :)
export default function SplashPage({ onEnter }) {
  const [isLeaving, setIsLeaving] = useState(false)

  // fade out first, THEN actually leave. looks way smoother than just popping away
  function startLeaving() {
    if (isLeaving) return
    setIsLeaving(true)
    setTimeout(onEnter, 450)
  }

  // pressing enter also works, for the keyboard people
  useEffect(() => {
    function listenForEnter(e) {
      if (e.key === 'Enter') startLeaving()
    }
    window.addEventListener('keydown', listenForEnter)
    return () => window.removeEventListener('keydown', listenForEnter)
  })

  return (
    <main className={`splash ${isLeaving ? 'splash--leaving' : ''}`}>
      <div className="splash__glow splash__glow--teal" />
      <div className="splash__glow splash__glow--coral" />
      <div className="splash__card">
        <img className="splash__logo" src="/spotter-logo.png" alt="Spotter AI logo" />
        <h1 className="splash__title">Welcome to my Project</h1>
        <p className="splash__subtitle">
          Weather-Aware Truck Routing &middot; pick the safest road for your load
        </p>
        <div className="splash__dots" aria-hidden="true">
          <span className="dot dot--coral" />
          <span className="dot dot--teal" />
          <span className="dot dot--light" />
          <span className="dot dot--light" />
        </div>
        <button className="splash__button" onClick={startLeaving} autoFocus>
          Start planning &rarr;
        </button>
        <p className="splash__hint">or press Enter</p>
      </div>
    </main>
  )
}
