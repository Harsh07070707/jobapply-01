import { createContext, useContext, useState, ReactNode, useEffect } from "react";

interface SearchState {
  lastSearchJobIds: string[] | null;
  showAllJobs: boolean;
  hasSearched: boolean;
  filter: string;
  query: string;
  sort: "fit" | "title" | "workspace";
  currentPage: number;
}

interface SearchStateContextType {
  state: SearchState;
  setLastSearchJobIds: (ids: string[] | null) => void;
  setShowAllJobs: (show: boolean) => void;
  setHasSearched: (searched: boolean) => void;
  setFilter: (filter: string) => void;
  setQuery: (query: string) => void;
  setSort: (sort: "fit" | "title" | "workspace") => void;
  setCurrentPage: (page: number) => void;
  clearAllState: () => void;
}

const SearchStateContext = createContext<SearchStateContextType | undefined>(undefined);

const DEFAULT_STATE: SearchState = {
  lastSearchJobIds: null,
  showAllJobs: false,
  hasSearched: false,
  filter: "all",
  query: "",
  sort: "fit",
  currentPage: 1,
};

export function SearchStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SearchState>(() => {
    // Initialize from sessionStorage on first mount
    try {
      const saved = sessionStorage.getItem("search_state");
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error("Failed to parse search state:", e);
    }
    return DEFAULT_STATE;
  });

  // Persist to sessionStorage whenever state changes
  useEffect(() => {
    sessionStorage.setItem("search_state", JSON.stringify(state));
  }, [state]);

  const setLastSearchJobIds = (ids: string[] | null) => {
    setState(prev => ({ ...prev, lastSearchJobIds: ids }));
  };

  const setShowAllJobs = (show: boolean) => {
    setState(prev => ({ ...prev, showAllJobs: show }));
  };

  const setHasSearched = (searched: boolean) => {
    setState(prev => ({ ...prev, hasSearched: searched }));
  };

  const setFilter = (filter: string) => {
    setState(prev => ({ ...prev, filter }));
  };

  const setQuery = (query: string) => {
    setState(prev => ({ ...prev, query }));
  };

  const setSort = (sort: "fit" | "title" | "workspace") => {
    setState(prev => ({ ...prev, sort }));
  };

  const setCurrentPage = (page: number) => {
    setState(prev => ({ ...prev, currentPage: page }));
  };

  const clearAllState = () => {
    setState(DEFAULT_STATE);
    sessionStorage.removeItem("search_state");
  };

  return (
    <SearchStateContext.Provider
      value={{
        state,
        setLastSearchJobIds,
        setShowAllJobs,
        setHasSearched,
        setFilter,
        setQuery,
        setSort,
        setCurrentPage,
        clearAllState,
      }}
    >
      {children}
    </SearchStateContext.Provider>
  );
}

export function useSearchState() {
  const context = useContext(SearchStateContext);
  if (!context) {
    throw new Error("useSearchState must be used within SearchStateProvider");
  }
  return context;
}
