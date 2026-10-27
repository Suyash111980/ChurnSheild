import { createContext, useContext, useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";

const NavigationTransitionContext = createContext({ generation: 0, reportReady: () => {}, beginDataTransition: () => {} });

export function NavigationTransitionProvider({ value, children }) {
  return <NavigationTransitionContext.Provider value={value}>{children}</NavigationTransitionContext.Provider>;
}

export function usePageTransitionReady(ready) {
  const { pathname } = useLocation();
  const { generation, reportReady } = useContext(NavigationTransitionContext);
  useLayoutEffect(() => {
    if (ready) reportReady(pathname, generation);
  }, [pathname, generation, ready, reportReady]);
}

/** Starts the shared main-content loader for a same-route data scope change. */
export function useBeginDataTransition() {
  return useContext(NavigationTransitionContext).beginDataTransition;
}
