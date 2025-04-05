const About = ({ username, about: { skill, description, image_link } }) => {
  return (
    <div className="flex justify-between mx-5 sm:mx-10 mt-5 min-h-96 bg-frame_bg ">
      <div className="p-10 md:w-1/2 w-full ">
        {" "}
        <p className="capitalize text-center md:text-left text-text_color text-2xl font-semibold ">
          {" "}
          about Me
        </p>
        <p className="text-white text-5xl font-bold mt-10 text-center md:text-left">
          {" "}
          I am a <span className="capitalize">{skill}</span>
        </p>
        <p className="mt-8 text-white text-center md:text-left">
          {" "}
          {description}
        </p>
      </div>
      <div className="hidden  md:flex items-stretch">
        <img
          src={image_link}
          alt={username}
          className="w-96 h-full object-cover"
        />
      </div>
    </div>
  );
};

export default About;
