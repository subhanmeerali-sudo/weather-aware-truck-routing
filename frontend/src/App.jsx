import { useState } from 'react'
import SplashPage from './components/SplashPage.jsx'
import PlannerPage from './components/PlannerPage.jsx'

// the whole app is just 2 screens: the welcome splash, then the planner
export default function App() {
  const [splashIsShowing, setSplashIsShowing] = useState(true)

  // the button on the splash calls this to make it go away (bye splash)
  function makeSplashGoAway() {
    setSplashIsShowing(false)
  }

  return splashIsShowing ? <SplashPage onEnter={makeSplashGoAway} /> : <PlannerPage />
}
