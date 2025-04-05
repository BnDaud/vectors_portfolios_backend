import { useEffect, useState } from "react";

const Portfolio = ({ username, portfolio }) => {
  //console.log(portfolio);
  const [categories, setCategories] = useState([]);

  const [display, setDisplay] = useState("All");

  const changeDisplay = (new_display) => {
    setDisplay(new_display);
  };
  useEffect(() => {
    const newcategories = [];

    portfolio.forEach((k) => {
      if (
        !newcategories.includes(k.category) &&
        !categories.includes(k.category)
      ) {
        newcategories.push(k.category);
      }
    });

    if (newcategories.length > 0) {
      setCategories((prevCategories) => [...prevCategories, ...newcategories]);
      newcategories.length = 0; // empty it
    }
  }, [portfolio]);

  return (
    <div className=" mt-5 bg-frame_bg mx-5 sm:mx-10">
      <h4 className="text-text_color text-center text-2xl pt-3 font-semibold">
        My Portfolio
      </h4>
      <div className="mt-5">
        <div className=" flex flex-wrap gap-x-4 gap-y-2 justify-center px-2 ">
          <p
            className={`text-sm cursor-pointer mb-3 ${
              display === "All" ? "text-text_color " : "text-white"
            }`}
            onClick={() => {
              changeDisplay("All");
            }}
          >
            {" "}
            {categories.length === 0 ? "No Portfolio" : "All"}
          </p>
          {categories.map((p) => {
            return (
              <p
                className={`text-sm cursor-pointer ${
                  display === p ? "text-text_color " : "text-white"
                }`}
                onClick={() => {
                  changeDisplay(p);
                }}
              >
                {" "}
                {p}
              </p>
            );
          })}
        </div>
      </div>{" "}
      <div className="flex flex-wrap gap-2 px-4 justify-center mt-3">
        {display === "All"
          ? portfolio.map((p) => {
              return (
                <a
                  href={p.project_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block relative w-72 h-72 text-white hover:text-text_color rounded-lg bg-center bg-no-repeat"
                  style={{
                    backgroundImage: `url(${p.thumbnail})`,
                    backgroundSize: "100% 100%",
                  }}
                >
                  <div className="absolute right-5 bottom-5 ">
                    <div className="text-2xl">{p.category}</div>
                    <div> {p.name}</div>
                  </div>
                </a>
              );
            })
          : portfolio.map((p) => {
              return (
                <div>
                  {" "}
                  {p.category === display ? (
                    <a
                      href={p.project_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block relative w-72 h-72 text-white hover:text-text_color rounded-lg bg-center bg-no-repeat"
                      style={{
                        backgroundImage: `url(${p.thumbnail})`,
                        backgroundSize: "100% 100%",
                      }}
                    >
                      <div className="absolute right-5 bottom-5 ">
                        <div className="text-2xl">{p.category}</div>
                        <div> {p.name}</div>
                      </div>
                    </a>
                  ) : (
                    ""
                  )}
                </div>
              );
            })}
      </div>
    </div>
  );
};

export default Portfolio;
