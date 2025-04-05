import { IoSchool } from "react-icons/io5";
import { GiSkills } from "react-icons/gi";
import { AiFillExperiment } from "react-icons/ai";
import { useState } from "react";

const Resume = ({ username, about: { resume, school, profiency } }) => {
  const [showexperience, setShowexperience] = useState(true);
  const [showeducation, setShoweducation] = useState(false);
  const [showskill, setShowskills] = useState(false);
  return (
    <div className=" mt-5 bg-frame_bg mx-5 sm:mx-10">
      <h4 className="text-text_color text-center text-2xl pt-3 font-semibold">
        My Resume
      </h4>
      {/*  show experience */}
      <div className="md:flex block gap-4 px-10  w-full mt-5">
        <div className={`w-1/2 mb-5 ${showexperience ? "block" : "hidden"}`}>
          <p className=" text-text_color text-xl uppercase leading-5 ">
            Experience
          </p>
          <p className="mt-5 sm:text-5xl text-2xl font-bold lowercase text-white ">
            <span className="uppercase">m</span>ore Than {7} years experience as
            a
          </p>
          <p className="text-text_color capitalize text-5xl  font-bold leading-16">
            {" fullstack"}
          </p>
        </div>

        <ul
          className={`${
            showexperience ? "block" : "hidden"
          }  list-none  min-h-40 mb-5  border-l-2 border-l-white`}
        >
          {resume.map((r) => {
            return (
              <li className="flex gap-2 mb-2 items-baseline">
                <div className="w-4 h-4 rounded-full bg-white -ml-2"></div>
                <div>
                  {" "}
                  <div className="text-white font-semibold capitalize text-xl">
                    {r.company_name}
                  </div>{" "}
                  <div className="text-white font-light">
                    {" "}
                    {`${r.post} (${r.start_year.split("-")[0]} - ${
                      r.end_year.split("-")[0]
                    })`}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {/* show Education*/}

        <div className={`w-1/2 mb-5 ${showeducation ? "block" : "hidden"}`}>
          <p className=" text-text_color text-xl uppercase leading-5 ">
            Education
          </p>
          <p className="mt-5 sm:text-5xl text-2xl font-bold lowercase text-white ">
            <span className="uppercase">l</span>earning experiences in a few
            <span className="text-text_color capitalize text-5xl  font-bold leading-16">
              {" professional institution"}
            </span>
          </p>
        </div>

        <ul
          className={`${
            showeducation ? "block" : "hidden"
          }  list-none  min-h-40 mb-5  border-l-2 border-l-white`}
        >
          {school.map((s) => {
            return (
              <li className="flex gap-2 mb-2 items-baseline">
                <div className="w-4 h-4 rounded-full bg-white -ml-2"></div>
                <div>
                  {" "}
                  <div className="text-white font-semibold capitalize text-xl">
                    {s.school_name}
                  </div>{" "}
                  <div className="text-white font-light">
                    {" "}
                    {` (${s.start_year.split("-")[0]} - ${
                      s.end_year.split("-")[0]
                    })`}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        {/* show skills*/}

        <div className={`w-1/2 mb-5 ${showskill ? "block" : "hidden"}`}>
          <p className=" text-text_color text-xl uppercase leading-5 ">
            Skills
          </p>
          <p className="mt-5 sm:text-5xl text-2xl font-bold lowercase text-text_color ">
            <span className="text-white capitalize">W</span>
            <span className="text-white ">ith good </span> Personnal
          </p>
          <p className="mt-5 sm:text-5xl text-2xl font-bold  text-text_color">
            and Professional{" "}
          </p>
          <p className="mt-5 sm:text-5xl text-2xl font-bold  text-text_color">
            Skills
          </p>
        </div>
        <div
          className={`flex gap-4 items-baseline ${
            showskill ? "block" : "hidden"
          }`}
        >
          <div className="bg-white h-4 w-4 rounded-full"> </div>
          <div className="text-white capitalize text-xl font-bold w-full">
            {" "}
            Professional Skill
            {profiency.map((p) => {
              return (
                <>
                  <p className="text-white font-light text-sm">
                    {" "}
                    {p.skill_name}
                  </p>
                  <div className="relative w-full md:w-72 lg:w-96 h-2 my-3 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r   from-new_color to-text_color transition-all duration-500"
                      style={{ width: `${p.skill_range}%` }}
                    ></div>
                  </div>
                </>
              );
            })}
          </div>
        </div>
      </div>
      <div className="flex justify-center gap-4 mt-5">
        <AiFillExperiment
          className={`cursor-pointer text-2xl mb-3 ${
            showexperience ? "text-text_color" : "text-white "
          }`}
          onClick={() => {
            setShowexperience(true);
            setShoweducation(false);
            setShowskills(false);
          }}
        />
        <IoSchool
          className={`cursor-pointer text-2xl mb-3 ${
            showeducation ? "text-text_color" : "text-white "
          }`}
          onClick={() => {
            setShowexperience(false);
            setShoweducation(true);
            setShowskills(false);
          }}
        />
        <GiSkills
          className={`cursor-pointer text-2xl mb-3 ${
            showskill ? "text-text_color" : "text-white "
          }`}
          onClick={() => {
            setShowexperience(false);
            setShoweducation(false);
            setShowskills(true);
          }}
        />
      </div>
    </div>
  );
};

export default Resume;
