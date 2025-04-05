import { useState, createContext, useRef } from "react";
import Allprofiles from "./allprofiles";
import Individualprofile from "./individualprofile";

export const Globalcontext = createContext();

const Template = () => {
  const [currentpage, setCurrentpage] = useState("all_profiles");
  const [username, setUsername] = useState("");
  const sectionsref = {
    home: useRef(null),
    about: useRef(null),
    resume: useRef(null),
    portfolio: useRef(null),
    contact: useRef(null),
  };

  const scroll_to_section = (section) => {
    sectionsref[section.toLowerCase()]?.current?.scrollIntoView({
      behavior: "smooth",
    });
  };

  return (
    <Globalcontext.Provider
      value={{ currentpage, setCurrentpage, username, setUsername }}
    >
      <div className="pt-20">
        {" "}
        {/* Prevent content from being covered */}
        {/* Navbar */}
        <nav className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-10 backdrop-blur-md   bg-frame_bg/60 h-16 shadow-md ">
          <p
            className="hover:cursor-pointer pl-4 bg-gradient-to-r from-text_color to-new_color bg-clip-text text-transparent text-3xl font-bold"
            onClick={() => setCurrentpage("all_profiles")}
          >
            Vectored Matrix
          </p>

          <div
            className={`pr-19 flex gap-4 ${
              currentpage === "all_profiles" ? "hidden" : "block"
            }`}
          >
            {["home", "about", "resume", "portfolio", "contact"].map(
              (section) => (
                <p
                  key={section}
                  className="text-white text-md hover:cursor-pointer"
                  onClick={() => scroll_to_section(section)}
                >
                  {section.charAt(0).toUpperCase() + section.slice(1)}
                </p>
              )
            )}
          </div>
        </nav>
        {/* Page Content */}
        <div>
          {currentpage === "all_profiles" ? (
            <Allprofiles />
          ) : (
            <Individualprofile username={username} refs={sectionsref} />
          )}
        </div>
      </div>
    </Globalcontext.Provider>
  );
};

export default Template;
