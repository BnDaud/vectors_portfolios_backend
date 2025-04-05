import { useEffect, useState, useContext } from "react";
import Notyetloader from "./notyetloaded";
import { Globalcontext } from "./template";
import { all_profiles_url } from "./globalvalues";

const Allprofiles = () => {
  const [profiles, setProfiles] = useState([]);

  const { currentpage, setCurrentpage, setUsername } =
    useContext(Globalcontext);

  const url = all_profiles_url;

  useEffect(() => {
    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        setProfiles(data);
        console.log(data[0]);
      })
      .catch((err) => {
        console.log(err);
      });
  }, []);

  return (
    <>
      <div className="mt-10 mx-10   ">
        {profiles.length !== 0 ? (
          <div className="flex flex-wrap justify-center gap-6">
            {profiles.map(({ user: { username }, display_pic, about }) => {
              return (
                <div class="mb-3 py-8  px-8 max-w-sm  space-y-2  bg-frame_bg rounded-xl shadow-lg sm:py-4 sm:flex sm:items-center sm:space-y-0 sm:gap-x-6">
                  <img
                    class="block mx-auto h-24 w-24 rounded-full sm:mx-0 sm:shrink-0"
                    src={display_pic}
                    alt={username}
                  />
                  <div class="text-center space-y-2 sm:text-left">
                    <div class="space-y-0.5">
                      <p class="text-lg bg-gradient-to-r from-text_color to-new_color bg-clip-text text-transparent font-semibold capitalize">
                        {username}
                      </p>
                      <p class="text-white font-medium truncate max-w-26">
                        {about?.skill ? about.skill : "No Skill Found"}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setUsername(username);
                        setCurrentpage("");
                      }}
                      class=" px-4 py-1 text-sm text-text_color font-semibold rounded-full border border-text_color hover:text-white hover:bg-text_color hover:border-transparent focus:outline-none focus:ring-2 focus:ring-text_color focus:ring-offset-1"
                    >
                      View Profile
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <Notyetloader />
        )}
      </div>
      <div
        className={`flex justify-center mt-3  mx-10 ${
          profiles.length === 0 ? "hidden" : "block"
        }`}
      >
        <button class=" px-4 py-1 text-sm text-text_color  capitalize font-semibold rounded-full border border-text_color hover:text-white hover:bg-text_color hover:border-transparent focus:outline-none focus:ring-2 focus:ring-text_color focus:ring-offset-1">
          Add Porfolio
        </button>
      </div>
    </>
  );
};

export default Allprofiles;
