const Home = ({
  username,
  img,
  user: { first_name, last_name },
  about: { skill },
}) => {
  return (
    <div className="flex flex-col sm:flex-row justify-between mx-5 sm:mx-10 h-auto sm:h-96 bg-frame_bg mt-5 p-10 pt-20">
      <div>
        <p className="text-white font-mono uppercase text-xl sm:text-3xl">
          I am {last_name} {first_name}
        </p>
        <p className="text-4xl sm:text-6xl text-text_color font-bold capitalize mt-6 sm:mt-12">
          {skill}
        </p>
      </div>
      {/* Hide image on small screens */}
      <div className="hidden sm:flex w-56 h-56 rotate-45 overflow-hidden items-center justify-center border-4 border-white shadow-xl shadow-black">
        <img
          src={img}
          alt={username}
          className="-rotate-45 w-full h-full object-cover"
        />
      </div>
    </div>
  );
};

export default Home;
